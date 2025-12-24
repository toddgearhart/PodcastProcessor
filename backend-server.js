const express = require('express');
const multer = require('multer');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const util = require('util');
const axios = require('axios');
const FormData = require('form-data');
const crypto = require('crypto');

const execPromise = util.promisify(exec);
const app = express();

app.use(cors());
app.use(express.json());

// Create directories if they don't exist
const dirs = ['uploads', 'downloads', 'logs', 'data'];
dirs.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Encryption settings
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || crypto.randomBytes(32).toString('hex');
const CREDENTIALS_FILE = 'data/credentials.json';

// Simple encryption/decryption
function encrypt(text) {
  const cipher = crypto.createCipher('aes-256-cbc', ENCRYPTION_KEY);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return encrypted;
}

function decrypt(encrypted) {
  const decipher = crypto.createDecipher('aes-256-cbc', ENCRYPTION_KEY);
  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

// Save credentials
function saveCredentials(credentials) {
  const encrypted = {
    fileBrowser: {
      url: credentials.fileBrowser.url,
      username: credentials.fileBrowser.username,
      password: encrypt(credentials.fileBrowser.password)
    },
    wordpress: {
      url: credentials.wordpress.url,
      username: credentials.wordpress.username,
      password: encrypt(credentials.wordpress.password)
    },
    podcast: credentials.podcast
  };
  
  fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(encrypted, null, 2));
}

// Load credentials
function loadCredentials() {
  try {
    if (!fs.existsSync(CREDENTIALS_FILE)) {
      return null;
    }
    
    const encrypted = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, 'utf8'));
    
    return {
      fileBrowser: {
        url: encrypted.fileBrowser.url,
        username: encrypted.fileBrowser.username,
        password: decrypt(encrypted.fileBrowser.password)
      },
      wordpress: {
        url: encrypted.wordpress.url,
        username: encrypted.wordpress.username,
        password: decrypt(encrypted.wordpress.password)
      },
      podcast: encrypted.podcast
    };
  } catch (error) {
    console.error('Error loading credentials:', error);
    return null;
  }
}

// Check if credentials are configured
function areCredentialsConfigured() {
  return fs.existsSync(CREDENTIALS_FILE);
}

const storage = multer.diskStorage({
  destination: './uploads/',
  filename: (req, file, cb) => {
    cb(null, Date.now() + '-' + file.originalname);
  }
});

const upload = multer({ 
  storage,
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'audio/wav' || file.originalname.toLowerCase().endsWith('.wav')) {
      cb(null, true);
    } else {
      cb(new Error('Only WAV files allowed'));
    }
  }
});

// API endpoint to get credentials status (without passwords)
app.get('/credentials', (req, res) => {
  const credentials = loadCredentials();
  
  if (!credentials) {
    res.json({ configured: false });
    return;
  }
  
  res.json({
    configured: true,
    fileBrowser: {
      url: credentials.fileBrowser.url,
      username: credentials.fileBrowser.username
    },
    wordpress: {
      url: credentials.wordpress.url,
      username: credentials.wordpress.username
    },
    podcast: credentials.podcast
  });
});

// API endpoint to save credentials
app.post('/credentials', (req, res) => {
  try {
    const { fileBrowser, wordpress, podcast } = req.body;
    
    if (!fileBrowser || !wordpress || !podcast) {
      return res.status(400).json({ error: 'Missing required credentials' });
    }
    
    saveCredentials({ fileBrowser, wordpress, podcast });
    res.json({ success: true, message: 'Credentials saved successfully' });
  } catch (error) {
    console.error('Error saving credentials:', error);
    res.status(500).json({ error: 'Failed to save credentials' });
  }
});

// API endpoint to test credentials
app.post('/test-credentials', async (req, res) => {
  const { fileBrowser, wordpress } = req.body;
  const results = { success: true, tests: {} };
  
  // Test FileBrowser
  try {
    const fbResponse = await axios.post(
      `${fileBrowser.url}/api/login`,
      {
        username: fileBrowser.username,
        password: fileBrowser.password
      }
    );
    results.tests.fileBrowser = { success: true, message: 'Connected successfully' };
  } catch (error) {
    results.success = false;
    results.tests.fileBrowser = { 
      success: false, 
      message: error.response?.data?.message || error.message 
    };
  }
  
  // Test WordPress
  try {
    const auth = Buffer.from(
      `${wordpress.username}:${wordpress.password.replace(/\s/g, '')}`
    ).toString('base64');
    
    const wpResponse = await axios.get(
      `${wordpress.url}/wp-json/wp/v2/users/me`,
      {
        headers: { 'Authorization': `Basic ${auth}` }
      }
    );
    results.tests.wordpress = { success: true, message: 'Connected successfully' };
  } catch (error) {
    results.success = false;
    results.tests.wordpress = { 
      success: false, 
      message: error.response?.data?.message || error.message 
    };
  }
  
  res.json(results);
});

// Process audio with ffmpeg
async function processAudio(inputPath, outputPath) {
  const command = `ffmpeg -i "${inputPath}" \
    -af "acompressor=threshold=-20dB:ratio=4:attack=5:release=50,loudnorm=I=-14:TP=-1.5:LRA=11" \
    -codec:a libmp3lame -b:a 128k -ac 2 \
    "${outputPath}"`;
  
  try {
    await execPromise(command);
    return true;
  } catch (error) {
    console.error('FFmpeg error:', error);
    throw error;
  }
}

// Upload to FileBrowser
async function uploadToFileBrowser(filePath, filename, year, config, statusCallback) {
  try {
    statusCallback('Logging into FileBrowser...');
    const loginResponse = await axios.post(
      `${config.url}/api/login`,
      {
        username: config.username,
        password: config.password
      }
    );
    
    const token = loginResponse.data;
    
    try {
      await axios.post(
        `${config.url}/api/resources/${year}`,
        {},
        {
          headers: { 'X-Auth': token }
        }
      );
    } catch (err) {
      // Folder might already exist
    }
    
    statusCallback('Uploading to FileBrowser...');
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    
    await axios.post(
      `${config.url}/api/resources/${year}/${filename}`,
      form,
      {
        headers: {
          ...form.getHeaders(),
          'X-Auth': token
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity
      }
    );
    
    return `${config.url}/api/public/dl/${year}/${filename}`;
    
  } catch (error) {
    console.error('FileBrowser upload error:', error.response?.data || error.message);
    throw new Error('Failed to upload to FileBrowser: ' + (error.response?.data?.message || error.message));
  }
}

// Get WordPress category ID by name
async function getWordPressCategoryId(categoryName, config) {
  try {
    const auth = Buffer.from(
      `${config.username}:${config.password.replace(/\s/g, '')}`
    ).toString('base64');
    
    const response = await axios.get(
      `${config.url}/wp-json/wp/v2/categories?search=${encodeURIComponent(categoryName)}`,
      {
        headers: { 'Authorization': `Basic ${auth}` }
      }
    );
    
    if (response.data && response.data.length > 0) {
      return response.data[0].id;
    }
    return null;
  } catch (error) {
    console.error('Error fetching category:', error.response?.data || error.message);
    return null;
  }
}

// Create WordPress draft post
async function createWordPressDraft(title, podcastUrl, date, config, statusCallback) {
  try {
    statusCallback('Creating WordPress draft...');
    
    const auth = Buffer.from(
      `${config.username}:${config.password.replace(/\s/g, '')}`
    ).toString('base64');
    
    const categoryId = await getWordPressCategoryId('Podcasts', config);
    
    const dateObj = new Date(date);
    const formattedDate = `${String(dateObj.getMonth() + 1).padStart(2, '0')}/${String(dateObj.getDate()).padStart(2, '0')}/${dateObj.getFullYear()}`;
    
    const postTitle = `${formattedDate} | ${title} | SUNDAY SERVICE`;
    
    const content = `
      <div class="podcast-audio">
        <audio controls style="width: 100%; max-width: 600px;">
          <source src="${podcastUrl}" type="audio/mpeg">
          Your browser does not support the audio element.
        </audio>
        <p><a href="${podcastUrl}" download>Download MP3</a></p>
      </div>
      <p><strong>Podcast URL:</strong> ${podcastUrl}</p>
      <p><em>Note: Add this URL to the "Media-Input-Podcast" custom field.</em></p>
    `;
    
    const postData = {
      title: postTitle,
      content: content,
      status: 'draft',
      date: date,
    };
    
    if (categoryId) {
      postData.categories = [categoryId];
    }
    
    const response = await axios.post(
      `${config.url}/wp-json/wp/v2/posts`,
      postData,
      {
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    try {
      await axios.post(
        `${config.url}/wp-json/wp/v2/posts/${response.data.id}`,
        {
          meta: { 'Media-Input-Podcast': podcastUrl }
        },
        {
          headers: {
            'Authorization': `Basic ${auth}`,
            'Content-Type': 'application/json'
          }
        }
      );
    } catch (metaError) {
      console.log('Could not set custom field automatically. User will need to add manually.');
    }
    
    return {
      postId: response.data.id,
      editLink: `${config.url}/wp-admin/post.php?post=${response.data.id}&action=edit`,
      previewLink: response.data.link
    };
    
  } catch (error) {
    console.error('WordPress error:', error.response?.data || error.message);
    throw new Error('Failed to create WordPress post: ' + (error.response?.data?.message || error.message));
  }
}

app.post('/upload', upload.single('file'), async (req, res) => {
  // Check if credentials are configured
  if (!areCredentialsConfigured()) {
    return res.status(400).json({ 
      error: 'Credentials not configured. Please configure credentials first.' 
    });
  }
  
  const credentials = loadCredentials();
  
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  
  const sendStatus = (status) => {
    res.write(`data: ${JSON.stringify({ status })}\n\n`);
  };
  
  try {
    if (!req.file) {
      res.write(`data: ${JSON.stringify({ error: 'No file uploaded' })}\n\n`);
      return res.end();
    }

    const { date, title } = req.body;
    
    if (!date || !title) {
      res.write(`data: ${JSON.stringify({ error: 'Date and title are required' })}\n\n`);
      return res.end();
    }

    const dateObj = new Date(date);
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    
    const sanitizedTitle = title.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const outputFilename = `${year}-${month}-${day}_${sanitizedTitle}.mp3`;
    const outputPath = path.join('downloads', outputFilename);

    sendStatus('Processing audio: applying compression...');
    await processAudio(req.file.path, outputPath);
    sendStatus('Audio processing complete: normalized to -14 LUFS');

    const fileBrowserUrl = await uploadToFileBrowser(
      outputPath, 
      outputFilename, 
      year.toString(), 
      credentials.fileBrowser, 
      sendStatus
    );
    sendStatus('File uploaded to FileBrowser');

    const podcastUrl = `${credentials.podcast.baseUrl}/${year}/${outputFilename}`;
    sendStatus(`Podcast URL generated: ${podcastUrl}`);

    const wpPost = await createWordPressDraft(
      title, 
      podcastUrl, 
      date, 
      credentials.wordpress, 
      sendStatus
    );
    sendStatus('WordPress draft created successfully');

    fs.unlinkSync(req.file.path);
    fs.unlinkSync(outputPath);

    res.write(`data: ${JSON.stringify({
      complete: true,
      message: 'File processed, uploaded, and WordPress draft created',
      mp3Name: outputFilename,
      fileBrowserUrl: fileBrowserUrl,
      podcastUrl: podcastUrl,
      year: year,
      wordpress: {
        postId: wpPost.postId,
        editLink: wpPost.editLink,
        previewLink: wpPost.previewLink
      }
    })}\n\n`);
    
    res.write('data: [DONE]\n\n');
    res.end();

  } catch (error) {
    console.error('Processing error:', error);
    
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
    
    res.write(`data: ${JSON.stringify({ 
      error: 'Failed to process file',
      details: error.message 
    })}\n\n`);
    res.end();
  }
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    credentialsConfigured: areCredentialsConfigured()
  });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Podcast Processor Backend running on port ${PORT}`);
  console.log(`Credentials configured: ${areCredentialsConfigured()}`);
});