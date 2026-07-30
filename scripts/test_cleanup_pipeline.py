import unittest

from scripts.benchmark_cleanup import (
    ensure_basic_formatting,
    preserves_content,
    reconcile_candidate,
)


class ReconcileCandidateTests(unittest.TestCase):
    def test_restores_speculative_words_without_losing_punctuation(self):
        original = (
            "linnell's pictures are a sort of up guards and atom paintings "
            "and mason's exquisite idols are as national as a jingo poem"
        )
        candidate = (
            "Linnell's pictures are a sort of up and down paintings, "
            "and Mason's exquisite idols are as national as a jingo poem."
        )

        reconciled = reconcile_candidate(original, candidate)

        self.assertEqual(
            reconciled,
            "Linnell's pictures are a sort of up guards and atom paintings, "
            "and Mason's exquisite idols are as national as a jingo poem.",
        )
        self.assertTrue(preserves_content(original, reconciled))

    def test_preserves_contextual_recognition_repairs(self):
        self.assertEqual(
            reconcile_candidate(
                "we check the result and return a final blow",
                "We check the result and return a final grade.",
            ),
            "We check the result and return a final grade.",
        )
        self.assertEqual(
            reconcile_candidate(
                "dictations for beginners true advanced",
                "Dictations for beginners through advanced students.",
            ),
            "Dictations for beginners through advanced students.",
        )

    def test_restores_dropped_and_invented_content_in_source_order(self):
        original = "i actually think we should keep every word because it matters"
        candidate = "I think we should add a clever summary because it matters."

        reconciled = reconcile_candidate(original, candidate)

        self.assertEqual(
            reconciled,
            "I actually think we should keep every word because it matters.",
        )


class BasicFormattingTests(unittest.TestCase):
    def test_adds_sentence_boundaries_without_changing_words(self):
        self.assertEqual(
            ensure_basic_formatting(
                "i actually think there are no good options",
                "i actually think there are no good options",
            ),
            "I actually think there are no good options.",
        )
        self.assertEqual(
            ensure_basic_formatting("how does it work", "how does it work"),
            "How does it work?",
        )


if __name__ == "__main__":
    unittest.main()
