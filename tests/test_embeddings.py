"""Small offline checks for document and question embeddings."""

import math
import unittest

from embeddings import EMBEDDING_DIMENSIONS, get_embedding, get_embeddings


class EmbeddingTests(unittest.TestCase):
    def test_embedding_has_expected_size_and_unit_length(self):
        vector = get_embedding("Machine learning training")
        self.assertEqual(len(vector), EMBEDDING_DIMENSIONS)
        self.assertAlmostEqual(math.sqrt(sum(value ** 2 for value in vector)), 1.0)

    def test_batch_preserves_order_and_matches_single_embeddings(self):
        texts = ["Machine learning", "PDF documents"]
        self.assertEqual(get_embeddings(texts), [get_embedding(text) for text in texts])
        self.assertEqual(get_embedding(texts[0]), get_embedding(texts[0]))

    def test_empty_inputs(self):
        self.assertEqual(get_embeddings([]), [])
        self.assertEqual(get_embedding(""), [0.0] * EMBEDDING_DIMENSIONS)


if __name__ == "__main__":
    unittest.main()
