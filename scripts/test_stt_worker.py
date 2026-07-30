import unittest

import numpy as np

from scripts.stt_worker import (
    FINAL_TRAILING_PADDING_SECONDS,
    FINAL_DIRECT_PASS_SECONDS,
    FINAL_TAIL_RESCUE_MIN_SECONDS,
    collapse_live_duplicate,
    merge_rolling_transcript,
    merge_final_segments,
    next_live_sample_target,
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

    def test_replaces_a_tiny_startup_hypothesis_after_name_revision(self):
        merged = merge_rolling_transcript(
            "mister Quilton's",
            "mister Quilter is the apostle of the middle classes",
        )

        self.assertEqual(
            merged,
            "mister Quilter is the apostle of the middle classes",
        )

    def test_does_not_append_an_unanchored_overlapping_window_twice(self):
        previous = (
            "Mister Carker used to flash his teeth and Mister John Collier "
            "gives his sitter a cheerful slap"
        )
        current = (
            "And Mr John Collier gives his sitter a cheerful slap on the back "
            "before he says next man"
        )

        merged = merge_rolling_transcript(previous, current)

        self.assertEqual(
            merged,
            "Mister Carker used to flash his teeth And Mr John Collier "
            "gives his sitter a cheerful slap on the back before he says next man",
        )

    def test_collapses_a_revised_clause_duplicated_inside_live_output(self):
        duplicated = (
            "Mister Carker used to flash his teeth. And Mr. John Collier gives "
            "his sitter a cheerful slap And mister John Audio gives His sitter "
            "a cheerful slap on the back before he says next man."
        )

        self.assertEqual(
            collapse_live_duplicate(duplicated),
            "Mister Carker used to flash his teeth. And Mr. John Collier gives "
            "his sitter a cheerful slap on the back before he says next man.",
        )

    def test_keeps_short_intentional_repetition(self):
        self.assertEqual(
            collapse_live_duplicate(
                "this is very very important and I really really mean it"
            ),
            "this is very very important and I really really mean it",
        )


class LiveCadenceTests(unittest.TestCase):
    def test_schedules_from_new_audio_when_recognition_is_fast(self):
        self.assertEqual(
            next_live_sample_target(16_000, 16_000, 1.0, 0.4),
            32_000,
        )

    def test_coalesces_audio_when_recognition_is_slower_than_requested_rate(self):
        self.assertEqual(
            next_live_sample_target(16_000, 16_000, 1.0, 2.0),
            56_000,
        )


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
        text, chunk_count, used_tail_rescue = transcribe_final(
            "parakeet",
            model,
            audio,
            sample_rate,
        )

        self.assertEqual(text, "complete transcript")
        self.assertEqual(chunk_count, 1)
        self.assertFalse(used_tail_rescue)
        self.assertEqual(model.calls, 2)

    def test_dedicated_tail_pass_restores_words_missing_from_long_final(self):
        sample_rate = 100
        timeline = np.arange(
            int(sample_rate * (FINAL_TAIL_RESCUE_MIN_SECONDS + 1)),
            dtype=np.float32,
        )
        audio = np.sin(timeline * 0.2).astype(np.float32)

        class FakeParakeet:
            def __init__(self):
                self.calls = 0

            def recognize(self, samples, sample_rate):
                self.calls += 1
                if self.calls == 1:
                    return "the long dictation reaches its final section"
                return "final section and preserves the last three words"

        model = FakeParakeet()
        text, chunk_count, used_tail_rescue = transcribe_final(
            "parakeet",
            model,
            audio,
            sample_rate,
        )

        self.assertEqual(
            text,
            "the long dictation reaches its final section and preserves the last three words",
        )
        self.assertEqual(chunk_count, 1)
        self.assertTrue(used_tail_rescue)

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

    def test_extended_audio_uses_long_context_chunks(self):
        sample_rate = 100
        audio = np.arange(sample_rate * 190, dtype=np.float32)

        chunks = split_final_audio(audio, sample_rate)

        self.assertEqual(len(chunks), 4)
        self.assertLessEqual(max(len(chunk) for chunk in chunks), sample_rate * 65)
        self.assertTrue(np.array_equal(chunks[0][:10], audio[:10]))
        self.assertTrue(np.array_equal(chunks[-1][-10:], audio[-10:]))

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
    collapse_live_duplicate,
