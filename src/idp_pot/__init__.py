from idp_pot.bedrock_processor import BedrockDocumentProcessor
from idp_pot.evaluation import evaluate_result
from idp_pot.evaluation_result import EvaluationResult
from idp_pot.processor_result import ProcessorResult
from idp_pot.textract_processor import TextractDocumentProcessor


def main() -> None:
    print("Hello from idp-pot!")


__all__ = [
    "BedrockDocumentProcessor",
    "EvaluationResult",
    "ProcessorResult",
    "TextractDocumentProcessor",
    "evaluate_result",
    "main",
]
