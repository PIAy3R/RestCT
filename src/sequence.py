from itertools import permutations
from typing import Set, List, Tuple

from rest import RestOp


class SCA:
    """
    SCA stands for "Sequence Covering Array"
    only cover the permutations of operations target at the same resource
    that is [post, delete, put, get]
    """

    def __init__(self, strength: int, uncovered: Set[Tuple[RestOp, RestOp]]):
        self._uncovered: Set[Tuple[RestOp, RestOp]] = uncovered
        self.strength = strength

    @classmethod
    def create_sca_model(cls, strength: int, available_ops: List[RestOp]):
        """
        Create a SCA model
        :param strength: the strength of the SCA model
        :param available_ops: a list of RestOp
        :return: a SCA model
        """
        uncovered: Set[Tuple[RestOp, ...]] = set()
        # group operations
        clusters: List[List[RestOp, ...]] = []
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

        def validate(permutation: Tuple[RestOp, ...]) -> bool:
            if len(permutation) == 0:
                raise ValueError("can not validate an empty permutation")
            for i, cur_op in enumerate(permutation):
                if cur_op.verb is RestOp.Method.POST and i != 0:
                    if any([cur_op.path.is_ancestor_of(pre_op) for pre_op in permutation[:i]]):
                        return False
                elif cur_op.verb is RestOp.Method.DELETE and i != (len(permutation) - 1):
                    if any([cur_op.path.is_ancestor_of(followed_op) or cur_op.path == followed_op.path for followed_op
                            in permutation[i + 1:]]):
                        return False
                else:
                    continue
            return True

        for c in clusters:
            if len(c) == 0:
                raise ValueError("unexpected empty cluster")
            real_strength = min(len(c), strength)
            for p in permutations(c, real_strength):
                if validate(p):
                    uncovered.add(p)
                else:
                    print(p)

        return uncovered


if __name__ == '__main__':
    from swagger import ParserV3

    parser = ParserV3("/Users/lixin/Workplace/Jupyter/work/swaggers/GitLab/Project.json")
    operations = parser.extract()
    sca = SCA.create_sca_model(2, operations)
