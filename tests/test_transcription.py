from app.transcription import paragraphs_from_segments


def test_transcript_segments_are_grouped_into_clean_paragraphs():
    result = paragraphs_from_segments(
        ["  First sentence.  ", "Second sentence!", "Third?", "Fourth.", "Fifth.", "Sixth."],
        sentences_per_paragraph=5,
    )
    assert result == (
        "First sentence. Second sentence! Third? Fourth. Fifth.\n\nSixth."
    )


def test_empty_transcript_segments_are_ignored():
    assert paragraphs_from_segments(["", "   "]) == ""

