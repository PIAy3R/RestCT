import json

from py2neo import Graph, Node, Relationship
from tqdm import tqdm

from src.config import Config
from src.swagger import SwaggerParser

file_path = "/Users/naariah/Documents/Python_Codes/api-suts/specifications/v3/gitlab-branch-13.json"
test_case_path = "/Users/naariah/Documents/Python_Codes/RestCT/out/test_data/case_response.json"


def connect_to_db():
    # connect to the database
    graph = Graph("bolt://localhost:7687", auth=("pzy", "12345678"), name="rest")
    return graph


def extract_swagger(swagger_path):
    config = Config()
    config.swagger = swagger_path
    parser = SwaggerParser(config)
    operations = parser.extract()
    return operations


def delete_all_nodes(graph):
    delete_all = "match (n) detach delete n"
    graph.run(delete_all)


def create_operation_node(graph, operations):
    for operation in tqdm(operations, desc="Creating Operation Nodes"):
        op_node = Node("Operation", name=operation.__repr__(), method=operation.verb.value,
                       path=operation.path.__repr__(),
                       description=operation.description)

        graph.merge(op_node, "Operation", "name")


def create_factor(graph, operations):
    for operation in tqdm(operations, desc=f"Creating Factor Nodes for Operations"):
        for parameter in operation.parameters:
            for factor in parameter.factor.get_leaves():
                if factor.description is None:
                    description = ""
                else:
                    description = factor.description
                factor_node = Node("Factor", name=factor.get_global_name, required=factor.required,
                                   description=description, format=factor.format,
                                   location=parameter.__class__.__name__)
                graph.merge(factor_node, "Factor", ("name", "required", "description", "location"))
                op_node = graph.nodes.match("Operation", name=operation.__repr__()).first()
                graph.create(Relationship(op_node, "has_factor", factor_node))


def creat_response_template(graph, operations):
    for operation in tqdm(operations, desc="Creating Response Nodes for Operations"):
        for response in operation.responses:
            if len(response.contents) > 0:
                content_type = response.contents[0][0]
                type = response.contents[0][1].__class__.__name__
            else:
                content_type = ""
                type = ""
            response_node = Node("ResponseTemplate", status_code=response.status_code, description=response.description,
                                 content_type=content_type, data_type=type)
            graph.merge(response_node, "ResponseTemplate", ("status_code", "description", "content_type", "data_type"))
            op_node = graph.nodes.match("Operation", name=operation.__repr__()).first()
            graph.create(Relationship(op_node, "has_response_template", response_node))
            if len(response.contents) > 0:
                for content in response.contents:
                    response_factor = content[1]
                    for f in response_factor.get_leaves():
                        if f.description is None:
                            description = ""
                        else:
                            description = f.description
                        response_factor_node = Node("Factor", name=f.get_global_name, required=f.required,
                                                    description=description, format=f.format, location="Response")
                        graph.create(response_factor_node)
                        graph.create(Relationship(response_node, "has_factor", response_factor_node))


def create_testcases(graph, operations, cases):
    for operation in tqdm(operations, desc="Creating Testcases for Operations"):
        op_cases = cases[operation.__repr__()]
        for info in op_cases:
            case = info[0]
            response_text = info[1]
            status_code = info[2]
            if int(status_code) // 100 == 2 or int(status_code) // 100 == 5:

                op_node = graph.nodes.match("Operation", name=operation.__repr__()).first()
                # total_cases
                match_all_cases = "MATCH (o:Operation{{{}}})-[r:has_case]->(c:Testcase) RETURN count(c)".format(
                    ":".join(["name", "'" + operation.__repr__() + "'"]))
                id = int(graph.run(match_all_cases).data()[0]["count(c)"]) + 1
                case_node = Node("Testcase", id=id, status_code=status_code)
                graph.create(case_node)
                response_node = Node("Response", text=str(response_text))
                graph.create(response_node)
                graph.create(Relationship(case_node, "has_response", response_node))
                graph.create(Relationship(op_node, "has_case", case_node))
                for factor in operation.get_leaf_factors():
                    if factor.get_global_name in case:
                        assignment_node = Node("Assignment", name=factor.get_global_name)
                        value = case[factor.get_global_name]
                        value_node = Node("Value", value=str(value))
                        # match = "MATCH (f:Factor{{{}}})-[r:has_assignment]->(a:Assignment) RETURN a".format(
                        #     ":".join(["name", "'" + factor.get_global_name + "'"]))
                        # assignment_node = graph.run(match).data()[0]["a"]
                        graph.create(assignment_node)
                        graph.merge(value_node, "Value", "value")
                        graph.create(Relationship(assignment_node, "has_value", value_node))
                        graph.create(Relationship(case_node, "has_assignment", assignment_node))


if __name__ == '__main__':
    graph = connect_to_db()
    operations = extract_swagger(file_path)
    with open(test_case_path, "r") as file:
        test_cases = json.load(file)
    delete_all_nodes(graph)
    create_operation_node(graph, operations)
    create_factor(graph, operations)
    creat_response_template(graph, operations)
    create_testcases(graph, operations, test_cases)
