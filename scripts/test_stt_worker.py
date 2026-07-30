import unittest

import numpy as np

from scripts.stt_worker import merge_rolling_transcript, prepare_final_audio


class PrepareFinalAudioTests(unittest.TestCase):
    def test_keeps_quiet_speech_when_trimmer_rejects_it(self):
        sample_rate = 16_000
        seconds = 1.0
        timeline = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
        quiet_speech = (0.006 * np.sin(2 * np.pi * 180 * timeline)).astype(np.float32)

        prepared = prepare_final_audio(quiet_speech, sample_rate)

        self.assertEqual(prepared.size, quiet_speech.size)
        self.assertGreater(float(np.sqrt(np.mean(prepared * prepared))), 0.01)

    def test_silence_remains_silence(self):
        sample_rate = 16_000
        prepared = prepare_final_audio(np.zeros(sample_rate, dtype=np.float32), sample_rate)

        self.assertEqual(prepared.size, sample_rate)
        self.assertEqual(float(np.max(np.abs(prepared))), 0.0)


class MergeRollingTranscriptTests(unittest.TestCase):
    def test_appends_only_new_words_from_an_overlapping_window(self):
        merged = merge_rolling_transcript(
            "one two three four five",
            "three four five six seven",
        )

        self.assertEqual(merged, "one two three four five six seven")

    def test_uses_newer_words_when_the_recognizer_revises_the_tail(self):
        merged = merge_rolling_transcript(
            "Parrot makes voice timing simple and grate",
            "voice timing simple and great for everyone",
        )

        self.assertEqual(
            merged,
            "Parrot makes voice timing simple and great for everyone",
        )

    def test_does_not_duplicate_a_repeated_window(self):
        merged = merge_rolling_transcript(
            "this is already visible",
            "this is already visible",
        )

        self.assertEqual(merged, "this is already visible")


if __name__ == "__main__":
    unittest.main()
