import unittest

import numpy as np

from scripts.stt_worker import (
    FINAL_TRAILING_PADDING_SECONDS,
    merge_rolling_transcript,
    prepare_final_audio,
    recover_live_tail,
)


class PrepareFinalAudioTests(unittest.TestCase):
    def test_keeps_quiet_speech_when_trimmer_rejects_it(self):
        sample_rate = 16_000
        seconds = 1.0
        timeline = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
        quiet_speech = (0.006 * np.sin(2 * np.pi * 180 * timeline)).astype(np.float32)

        prepared = prepare_final_audio(quiet_speech, sample_rate)

        expected_padding = int(sample_rate * FINAL_TRAILING_PADDING_SECONDS)
        self.assertEqual(prepared.size, quiet_speech.size + expected_padding)
        self.assertGreater(
            float(np.sqrt(np.mean(prepared[:-expected_padding] ** 2))),
            0.01,
        )
        self.assertEqual(float(np.max(np.abs(prepared[-expected_padding:]))), 0.0)

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


class RecoverLiveTailTests(unittest.TestCase):
    def test_restores_a_last_word_missing_from_the_final_pass(self):
        recovered = recover_live_tail(
            "We have hundreds of online dictations for beginners true advanced.",
            "We have hundreds of online dictations for beginners through advanced students.",
        )

        self.assertEqual(
            recovered,
            "We have hundreds of online dictations for beginners true advanced students.",
        )

    def test_restores_a_trailing_phrase_after_a_shared_anchor(self):
        recovered = recover_live_tail(
            "These dictations are designed for beginners.",
            "These dictations are designed for beginners through advanced students.",
        )

        self.assertEqual(
            recovered,
            "These dictations are designed for beginners through advanced students.",
        )

    def test_keeps_final_word_choice_when_live_pass_has_no_extra_tail(self):
        recovered = recover_live_tail(
            "You can receive a final grade.",
            "You can receive a final blow.",
        )

        self.assertEqual(recovered, "You can receive a final grade.")


if __name__ == "__main__":
    unittest.main()
