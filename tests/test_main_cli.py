import unittest

from main import build_parser


class MainCliTests(unittest.TestCase):
    def test_accepts_common_responses_tuning_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--input",
                "sample.xml",
                "--temperature",
                "0.35",
                "--top-p",
                "0.9",
                "--max-output-tokens",
                "2048",
                "--reasoning-effort",
                "high",
                "--verbosity",
                "low",
            ]
        )

        self.assertEqual(args.temperature, 0.35)
        self.assertEqual(args.top_p, 0.9)
        self.assertEqual(args.max_output_tokens, 2048)
        self.assertEqual(args.reasoning_effort, "high")
        self.assertEqual(args.verbosity, "low")

    def test_rejects_out_of_range_temperature(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["--input", "sample.xml", "--temperature", "2.5"])
