import random
from typing import Any, Dict, List, Optional

from transformers import DataCollatorForLanguageModeling, DataCollatorForWholeWordMask
from transformers.data.data_collator import _torch_collate_batch
from transformers.tokenization_utils_base import PreTrainedTokenizerBase


def tolist(x):
    if isinstance(x, list):
        return x
    elif hasattr(x, "numpy"):  # Checks for TF tensors without needing the import
        x = x.numpy()
    return x.tolist()


class DataCollatorForBert(DataCollatorForWholeWordMask):
    """
    Processing training examples to mini-batch for Bert (mlm+wwm+sop).
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        mlm_probability: float = 0.15,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.tokenizer = tokenizer
        self.mlm_probability = mlm_probability
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        examples = self._prepare_wwm_and_sop_from_examples(examples)
        batch = self.tokenizer.pad(examples, return_tensors="pt", pad_to_multiple_of=self.pad_to_multiple_of)
        batch_mask = batch.pop("mask_label")
        batch["input_ids"], batch["labels"] = self.torch_mask_tokens(batch["input_ids"], batch_mask)
        return batch

    def _prepare_wwm_and_sop_from_examples(self, examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output_examples = []
        for example in examples:
            chunk_ids = example["input_ids"]
            seq_length = len(chunk_ids)
            start, end = seq_length // 3, seq_length // 3 * 2
            split_position = random.randrange(start, end)
            reverse = random.random() < 0.5

            if reverse:
                token_a = chunk_ids[split_position:]
                token_b = chunk_ids[:split_position]
            else:
                token_a = chunk_ids[:split_position]
                token_b = chunk_ids[split_position:]

            input_ids = self.tokenizer.build_inputs_with_special_tokens(token_a, token_b)
            token_type_ids = self.tokenizer.create_token_type_ids_from_sequences(token_a, token_b)
            sentence_order_label = 1 if reverse else 0
            ref_tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
            mask_label = self._whole_word_mask(ref_tokens)

            output_examples.append(
                {
                    "input_ids": input_ids,
                    "token_type_ids": token_type_ids,
                    "next_sentence_label": sentence_order_label,
                    "mask_label": mask_label,
                }
            )
        return output_examples


class DataCollatorForAlbert(DataCollatorForLanguageModeling):
    """
    Processing training examples to mini-batch for Albert (mlm+sop).
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        mlm_probability: float = 0.15,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.tokenizer = tokenizer
        self.mlm_probability = mlm_probability
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        examples = self._prepare_sop_from_examples(examples)
        batch = self.tokenizer.pad(examples, return_tensors="pt", pad_to_multiple_of=self.pad_to_multiple_of)

        special_tokens_mask = batch.pop("special_tokens_mask", None)
        batch["input_ids"], batch["labels"] = self.torch_mask_tokens(
            batch["input_ids"], special_tokens_mask=special_tokens_mask
        )
        return batch

    def _prepare_sop_from_examples(self, examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output_examples = []
        for example in examples:
            chunk_ids = example["input_ids"]
            seq_length = len(chunk_ids)
            start, end = seq_length // 3, seq_length // 3 * 2
            split_position = random.randrange(start, end)
            reverse = random.random() < 0.5

            if reverse:
                token_a = chunk_ids[split_position:]
                token_b = chunk_ids[:split_position]
            else:
                token_a = chunk_ids[:split_position]
                token_b = chunk_ids[split_position:]

            input_ids = self.tokenizer.build_inputs_with_special_tokens(token_a, token_b)
            token_type_ids = self.tokenizer.create_token_type_ids_from_sequences(token_a, token_b)
            special_tokens_mask = self.tokenizer.get_special_tokens_mask(input_ids, already_has_special_tokens=True)
            sentence_order_label = 1 if reverse else 0

            output_examples.append(
                {
                    "input_ids": input_ids,
                    "token_type_ids": token_type_ids,
                    "special_tokens_mask": special_tokens_mask,
                    "sentence_order_label": sentence_order_label,
                }
            )
        return output_examples


class DataCollatorForRoberta(DataCollatorForLanguageModeling):
    """
    Processing training examples to mini-batch for Roberta (mlm).
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        mlm_probability: float = 0.15,
        pad_to_multiple_of: Optional[int] = None,
    ) -> None:
        super().__init__(
            tokenizer=tokenizer, mlm=True, mlm_probability=mlm_probability, pad_to_multiple_of=pad_to_multiple_of
        )


class DataCollatorForGpt2:
    """
    Processing training examples to mini-batch for Gpt2 (clm).
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, examples):
        examples = [example["input_ids"] for example in examples]
        batch = {
            "input_ids": _torch_collate_batch(
                examples, tokenizer=self.tokenizer, pad_to_multiple_of=self.pad_to_multiple_of
            )
        }
        batch["labels"] = batch["input_ids"].clone()
        return batch
