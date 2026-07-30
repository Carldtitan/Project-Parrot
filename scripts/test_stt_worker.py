import unittest

import numpy as np

from scripts.stt_worker import (
    FINAL_TRAILING_PADDING_SECONDS,
    FINAL_DIRECT_PASS_SECONDS,
    merge_rolling_transcript,
    merge_final_segments,
    prepare_final_audio,
    recover_live_tail,
    split_final_audio,
    transcribe_final,
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


class SplitFinalAudioTests(unittest.TestCase):
    def test_ordinary_long_dictation_uses_one_context_preserving_pass(self):
        sample_rate = 100
        timeline = np.arange(
            int(sample_rate * (FINAL_DIRECT_PASS_SECONDS - 1)),
            dtype=np.float32,
        )
        audio = np.sin(timeline * 0.2).astype(np.float32)

        class FakeParakeet:
            def __init__(self):
                self.calls = 0

            def recognize(self, samples, sample_rate):
                self.calls += 1
                return "complete transcript"

        model = FakeParakeet()
        text, chunk_count = transcribe_final(
            "parakeet",
            model,
            audio,
            sample_rate,
        )

        self.assertEqual(text, "complete transcript")
        self.assertEqual(chunk_count, 1)
        self.assertEqual(model.calls, 1)

    def test_long_audio_is_fully_covered_by_overlapping_chunks(self):
        sample_rate = 100
        audio = np.arange(sample_rate * 61, dtype=np.float32)

        chunks = split_final_audio(
            audio,
            sample_rate,
            chunk_seconds=18.0,
            overlap_seconds=1.5,
        )

        self.assertGreaterEqual(len(chunks), 4)
        self.assertLessEqual(max(len(chunk) for chunk in chunks), sample_rate * 20)
        self.assertTrue(np.array_equal(chunks[0][:10], audio[:10]))
        self.assertTrue(np.array_equal(chunks[-1][-10:], audio[-10:]))
        for previous, current in zip(chunks, chunks[1:]):
            self.assertGreater(
                len(np.intersect1d(previous[-200:], current[:200])),
                0,
            )

    def test_short_audio_stays_in_one_chunk(self):
        audio = np.ones(16_000 * 5, dtype=np.float32)

        chunks = split_final_audio(audio, 16_000)

        self.assertEqual(len(chunks), 1)
        self.assertTrue(np.array_equal(chunks[0], audio))

    def test_final_audio_preserves_soft_edges(self):
        sample_rate = 16_000
        quiet_edge = np.full(sample_rate, 0.005, dtype=np.float32)
        loud_middle = np.full(sample_rate, 0.08, dtype=np.float32)
        source = np.concatenate((quiet_edge, loud_middle, quiet_edge))

        prepared = prepare_final_audio(source, sample_rate)

        self.assertEqual(
            len(prepared),
            len(source) + int(sample_rate * FINAL_TRAILING_PADDING_SECONDS),
        )

    def test_final_merge_cannot_erase_an_old_common_phrase(self):
        previous = (
            "the first section keeps every important word and the shared phrase "
            "appears here before twelve unique closing words alpha beta gamma delta "
            "epsilon zeta eta theta iota kappa lambda mu"
        )
        current = "the shared phrase appears here and then the new ending arrives"

        merged = merge_final_segments(previous, current)

        self.assertIn("first section keeps every important word", merged)
        self.assertIn("alpha beta gamma delta", merged)

    def test_final_merge_keeps_words_missing_from_the_newer_overlap(self):
        previous = (
            "Mister Burkett Foster smiles and Mister Carker used to flash his teeth"
        )
        current = (
            "Mister Carker used and Mister John Collier gives his sitter a cheerful slap"
        )

        merged = merge_final_segments(previous, current)

        self.assertEqual(
            merged,
            "Mister Burkett Foster smiles and Mister Carker used to flash his teeth "
            "and Mister John Collier gives his sitter a cheerful slap",
        )

    def test_final_merge_uses_a_close_newer_boundary_word_once(self):
        merged = merge_final_segments(
            "Parrot makes voice timing simple and grate",
            "voice timing simple and great for everyone",
        )

        self.assertEqual(
            merged,
            "Parrot makes voice timing simple and great for everyone",
        )


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
