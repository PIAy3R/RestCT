from itertools import permutations, combinations
from random import choice
from typing import Set, List, Tuple, Dict, Union

from src.rest import RestOp, Method


class SCA:
    """
    SCA stands for "Sequence Covering Array"
    only cover the permutations of operations target at the same resource
    that is [post, delete, put, get]
    """

    def __init__(self, strength: int, available_ops: List[RestOp], uncovered: Dict[int, Set[Tuple[RestOp]]]):
        self._uncovered: Dict[int, Set[Tuple[RestOp]]] = uncovered
        self.strength: int = strength
        self.operations: List[RestOp] = available_ops

    @classmethod
    def create_sca_model(cls, strength: int, available_ops: List[RestOp]):
        """
        Create a SCA model
        :param strength: the strength of the SCA model
        :param available_ops: a list of RestOp
        :return: a SCA model
        """
        uncovered: Dict[int, Set[Tuple[RestOp]]] = {k: set() for k in range(1, strength + 1)}
        # group operations
        clusters: List[List[RestOp]] = []
        sorted_ops = sorted(available_ops, key=lambda x: len(x.path.elements), reverse=True)
        for op in sorted_ops:
            if len(clusters) == 0:
                clusters.append([op, ])
            else:
                new_cluster = True
                for c in clusters:
                    if any([op.path.is_ancestor_of(c_op.path) for c_op in c]):
                        c.append(op)
                        new_cluster = False

                if new_cluster:
                    clusters.append([op, ])

        def validate(permutation: Tuple[RestOp]) -> bool:
            if len(permutation) == 0:
                raise ValueError("can not validate an empty permutation")
            for i, cur_op in enumerate(permutation):
                if cur_op.verb is Method.POST and i != 0:
                    if any([cur_op.path.is_ancestor_of(pre_op.path) for pre_op in permutation[:i]]):
                        return False
                elif cur_op.verb is Method.DELETE and i != (len(permutation) - 1):
                    if any([cur_op.path.is_ancestor_of(followed_op.path) or cur_op.path == followed_op.path for
                            followed_op in permutation[i + 1:]]):
                        return False
                else:
                    continue
            return True

        max_strength = 0
        for c in clusters:
            if len(c) == 0:
                raise ValueError("unexpected empty cluster")
            real_strength = min(len(c), strength)
            for p in permutations(c, real_strength):
                if validate(p):
                    uncovered[len(p)].add(p)
                    max_strength = max(len(p), max_strength)
                else:
                    continue
        if max_strength < strength:
            raise ValueError("can not find a permutation of strength {}".format(strength))

        return SCA(strength, available_ops, uncovered)

    def extend(self, sequence: List[RestOp]) -> Union[List[RestOp], None]:
        # c_size: the size of combinations
        for c_len in range(self.strength - 1, -1, -1):
            if c_len > len(sequence):
                continue

            candidates = self._get_candidates(sequence)
            if len(candidates) == 0:
                continue

            priority, best = self._choose_best(candidates, sequence, c_len)
            if priority > 0:
                op_list_to_add = self._retrieve_dependent_ops(sequence, best)
                sequence.extend(op_list_to_add)
                sequence.append(best)
                return sequence
            else:
                if c_len == 0:
                    return sequence
        return sequence

    def _retrieve_dependent_ops(self, seq: List[RestOp], best: RestOp):
        ops: List[RestOp] = []
        for op in self.operations:
            if op in seq or op == best:
                continue
            if op.verb is Method.POST and op.path.is_ancestor_of(best.path):
                ops.append(op)

        return sorted(ops, key=lambda o: len(o.path.elements))

    def _get_candidates(self, seq: List[RestOp]):
        candidates = set()

        for op in self.operations:
            if op in seq:
                continue

            destroyed = False
            for member in seq:
                if member.verb is Method.DELETE and member.path.is_ancestor_of(op.path):
                    destroyed = True
                    break

            if not destroyed:
                candidates.add(op)

        return candidates

    def _choose_best(self, candidates: set[RestOp], seq: List[RestOp], c_len: int) -> tuple[int, Union[RestOp, None]]:
        """
        choose the best candidate for the next operation
        @return: the priority of the operation, and the list of preferred operations
        """
        if len(candidates) == 0:
            return 0, None

        filtered_candidates = set()
        max_count = 0
        for c in candidates:
            count = self._count_permutation_with_op(c, seq, c_len)
            if count == max_count:
                filtered_candidates.add(c)
            elif count > max_count:
                filtered_candidates = {c, }
                max_count = count
            else:
                continue
        return max_count, choice(list(filtered_candidates))

    def _count_permutation_with_op(self, c: RestOp, seq: List[RestOp], c_len: int) -> int:
        """
        Count the number of permutations with a given operation.
        @param c: the given candidate
        @param seq: the generated sequence
        @param c_len: the length of combinations
        @return: the number of permutations
        """
        count = 0
        for length, uncovered in self._uncovered.items():
            if len(uncovered) == 0:
                continue
            if length <= c_len:
                p_list = {op + (c,) for op in combinations(seq, length)}
                count += len(uncovered & p_list)
            else:
                p_list = {op + (c,) for op in combinations(seq, c_len)}
                for combination in uncovered:
                    if combination[:(c_len + 1)] in p_list:
                        count += 1
        return count


if __name__ == '__main__':
    from swagger import ParserV3

    parser = ParserV3("/Users/lixin/Workplace/Jupyter/work/swaggers/GitLab/Project.json")
    operations = parser.extract()
    sca = SCA.create_sca_model(2, operations)
    while len(sca._uncovered) > 0:
        s = []
        length = -1
        while len(s) != length:
            length = len(s)
            s = sca.extend(s)
        print(s)
