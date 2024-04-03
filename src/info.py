from collections import defaultdict
from typing import List, Dict, Tuple, Set

from src.factor import Value, ValueType
from src.rest import RestOp


class RuntimeInfoManager:
    def __init__(self):
        self._num_of_requests = 0
        self.llm_call = 0
        self.call_time = 0
        self.prompt_tokens = 0
        self.cost = 0
        self._response_chains: List[Dict[str, object]] = [dict()]
        self._unresolved_params: Set[Tuple[RestOp, str]] = set()

        self._reused_essential_seq_dict: Dict[Tuple[RestOp], List[Dict[str, Value]]] = defaultdict(list)
        self._reused_all_p_seq_dict: dict = defaultdict(list)
        self._ok_value_dict: Dict[str, List[Value]] = defaultdict(list)
        self._success_sequence: set = set()

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

    def is_unresolved(self, p_name):
        return p_name in self._unresolved_params

    def save_reuse(self, url_tuple, is_essential, case):
        if is_essential:
            to_dict = self._reused_essential_seq_dict
        else:
            to_dict = self._reused_all_p_seq_dict
        if len(to_dict[url_tuple]) < 10:
            to_dict[url_tuple].append(case)

    def save_ok_value(self, case):
        for paramStr, value in case.items():
            if paramStr not in self._ok_value_dict.keys():
                self._ok_value_dict[paramStr].append(value)
            else:
                lst = self._ok_value_dict.get(paramStr)
                if len(lst) < 10 and value not in lst:
                    lst.append(value)

    def save_chain(self, chain, operation, response):
        new_chain = chain.copy()
        new_chain[operation] = response
        self._response_chains.append(new_chain)
        if len(self._response_chains) > 10:
            self._response_chains.pop(0)

    @staticmethod
    def save_id_count(operation, response, id_counter):
        if isinstance(response, dict):
            iid = response.get("id")
            try:
                id_counter.append((iid, operation.path.__repr__()))
            except TypeError:
                pass
        elif isinstance(response, list):
            for r in response:
                iid = r.get("id")
                try:
                    id_counter.append((int(iid), operation.url))
                except TypeError:
                    pass
        else:
            pass

    def save_success_seq(self, url_tuple):
        self._success_sequence.add(url_tuple)
