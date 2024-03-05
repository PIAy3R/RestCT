from collections import defaultdict
from typing import List, Dict, Tuple

from src.Dto.factor import Value, ValueType
from src.Dto.rest import RestOp


class RuntimeInfoManager:
    def __init__(self):
        self._num_of_requests = 0
        self.llm_call = 0
        self.call_time = 0
        self.prompt_tokens = 0
        self.cost = 0
        self._response_chains: List[Dict[str, object]] = [dict()]

        self._reused_essential_seq_dict: Dict[Tuple[RestOp], List[Dict[str, Value]]] = defaultdict(list)
        self._reused_all_p_seq_dict: dict = defaultdict(list)

    def get_chains(self, max_chain_items):
        sortedList = sorted(self._response_chains, key=lambda c: len(c.keys()), reverse=True)
        return sortedList[:max_chain_items] if max_chain_items < len(sortedList) else sortedList

    def get_reused_with_essential_p(self, operations: Tuple[RestOp]):
        reused_case = self._reused_essential_seq_dict.get(operations, list())
        if len(reused_case) > 0:
            return [{p: Value(v.val, ValueType.Reused, v.type) for p, v in case.items()} for case in reused_case]
        return []

    def get_reused_with_all_p(self, operations: Tuple[RestOp]):
        reused_case = self._reused_all_p_seq_dict.get(operations, list())
        if len(reused_case) > 0:
            return [{p: Value(v.val, ValueType.Reused, v.type) for p, v in case.items()} for case in reused_case]
        return []
