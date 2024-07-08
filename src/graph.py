import json
from collections import defaultdict

from py2neo import Graph, Node, Relationship
from tqdm import tqdm

from src.config import Config
from src.swagger import SwaggerParser

# paths
file_path = "/Users/naariah/Documents/Python_Codes/api-suts/specifications/v3/gitlab-branch-13.json"
test_case_path = "/Users/naariah/Documents/Python_Codes/RestCT/out/test_data/case_response.json"


def extract_swagger(swagger_path):
    config = Config()
    config.swagger = swagger_path
    parser = SwaggerParser(config)
    operations = parser.extract()
    return operations


def connect_to_db():
    """
    Connect to the Neo4j database
    """
    graph = Graph("bolt://localhost:7687", auth=("pzy", "12345678"), name="rest")
    return graph


def delete_all(graph):
    """
    Delete all nodes and relationships in the database
    """
    cypher_delete_all = "match (n) detach delete n"
    graph.run(cypher_delete_all)


def create_operation_nodes(graph, operations):
    """
    Create nodes for operations
    """
    for operation in tqdm(operations, desc="Creating Operation Nodes"):
        op_node = Node("Operation", name=operation.__repr__(), method=operation.verb.value,
                       path=operation.path.__repr__(),
                       description=operation.description)

        graph.merge(op_node, "Operation", "name")


def create_nodes_and_relations_related_to_factors(graph, operations):
    """
    Create nodes for factors and their relationships with operations
    """
    for operation in tqdm(operations, desc=f"Creating Factor Nodes for Operations"):
        for parameter in operation.parameters:
            for factor in parameter.factor.get_leaves():
                if factor.description is None:
                    description = ""
                else:
                    description = factor.description
                factor_node = Node("Factor", name=factor.get_global_name, required=factor.required,
                                   description=description, format=factor.format,
                                   location=parameter.__class__.__name__, type=factor.__class__.__name__)
                graph.merge(factor_node, "Factor", ("name", "required", "description", "location", "type"))
                op_node = graph.nodes.match("Operation", name=operation.__repr__()).first()
                graph.create(Relationship(op_node, "has_factor", factor_node))


def create_nodes_and_relations_related_to_response_templates(graph, operations):
    """
    Create nodes for response templates and their relationships with operations
    """
    for operation in tqdm(operations, desc="Creating Response Nodes for Operations"):
        for response in operation.responses:
            if len(response.contents) > 0:
                content_type = response.contents[0][0]
                data_type = response.contents[0][1].__class__.__name__
            else:
                content_type = ""
                data_type = ""
            response_node = Node("ResponseTemplate", status_code=response.status_code, description=response.description,
                                 content_type=content_type, data_type=data_type)
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
                                                    description=description, format=f.format, location="Response",
                                                    type=f.__class__.__name__)
                        graph.create(response_factor_node)
                        graph.create(Relationship(response_node, "has_factor", response_factor_node))


def create_nodes_and_relations_related_to_testcases(graph, operations, cases):
    """
    Create nodes for testcases and their relationships with operations
    """
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
                status = None
                case_node = Node("Testcase", id=id, status_code=status_code, operation=operation.__repr__(),
                                 status=status)

                if int(status_code) // 100 == 2:
                    if operation.verb.value == "post":
                        status = "existed"
                    elif operation.verb.value == "delete":
                        status = "deleted"
                if operation.verb.value in ["post", "delete"]:
                    test_resource_node = Node("TestResource", id=id, properties=json.dumps(response_text),
                                              status=status,
                                              operation=operation.__repr__())
                    cypher_system_resource = "MATCH (s:SystemResource)-[r:has_operation]->(o:Operation{{name:'{}'}}) RETURN s".format(
                        operation.__repr__())
                    system_resource_node = graph.run(cypher_system_resource).data()[0]["s"]
                    graph.merge(test_resource_node, "TestResource", ("id", "properties", "status", "operation"))
                    graph.create(Relationship(system_resource_node, "has_resource", test_resource_node))

                graph.merge(case_node, "Testcase", ("id", "operation"))
                response_node = Node("Response", text=json.dumps(response_text), status_code=status_code)
                graph.create(response_node)
                graph.create(Relationship(op_node, "has_case", case_node))
                graph.create(Relationship(case_node, "has_response", response_node))
                for factor in operation.get_leaf_factors():
                    if factor.get_global_name in case:
                        assignment_node = Node("Assignment", name=factor.get_global_name,
                                               type=factor.__class__.__name__)
                        value = case[factor.get_global_name]
                        value_node = Node("Value", value=str(value),
                                          type=factor.__class__.__name__.replace("Factor", "").lower())
                        graph.create(assignment_node)
                        graph.merge(value_node, "Value", "value")
                        graph.create(Relationship(assignment_node, "has_value", value_node))
                        graph.create(Relationship(case_node, "has_assignment", assignment_node))


def create_response_assignment(graph, operations):
    """
    Create nodes for response assignments and their relationships with responses, values
    """
    for operation in tqdm(operations, desc="Creating Response Parameters"):
        match_factors = "MATCH (o:Operation{{name:'{}'}})-[:has_response_template]->(r:ResponseTemplate)-[:has_factor]->(f:Factor) RETURN r, f".format(
            operation.__repr__())
        data = graph.run(match_factors).data()
        match_response = "MATCH (o:Operation{{name:'{}'}})-[:has_case]->(c:Testcase)-[:has_response]->(r:Response) RETURN r".format(
            operation.__repr__())
        response_nodes = [d.get("r") for d in graph.run(match_response).data()]
        for response in response_nodes:
            response_factors = []
            for template_factor in data:
                template = template_factor.get("r")
                if template.get("status_code") == response.get("status_code"):
                    response_factors.append(template_factor.get("f"))
            response_text = response.get("text")
            response_json = json.loads(response_text)
            for factor in response_factors:
                value = get_factor_value(response_json, factor)
                if value is not None:
                    assignment_node = Node("Assignment", name=factor.get("name"), type=factor.get("type"))
                    value_node = Node("Value", value=str(value), type=factor.get("type").replace("Factor", "").lower())
                    graph.create(assignment_node)
                    graph.merge(value_node, "Value", "value")
                    graph.create(Relationship(response, "has_assignment", assignment_node))
                    graph.create(Relationship(assignment_node, "has_value", value_node))


def get_factor_value(response, factor):
    """
    Get the value of a factor from a response
    """
    value = response
    factor_name = factor.get("name")
    items = factor_name.split(".")
    for item in items:
        if value is None:
            return None
        if item == "response":
            continue
        if item == "_item" and isinstance(value, list):
            if len(value) > 0:
                value = value[0]
            else:
                return None
        elif item == "_items" and not isinstance(value, list):
            return None
        else:
            value = value.get(item, None)
    return value


def get_response_value(operation, factor_name):
    """
    Get the value of a factor from a response after creating in the graph
    """
    match = "MATCH(n: Operation{{name:'{}'}})-[r1: has_case]->(c:Testcase)-[r2: has_response]->(r:Response)-[r3: has_assignment]->(a:Assignment{{name:'{}'}})-[r4: has_value]->(v:Value) RETURN n, r1, c, r2, r, r3, a, r4, v".format(
        operation.__repr__(), factor_name)
    matched = graph.run(match).data()
    value_list = []
    for chain in matched:
        value_list.append(chain.get("v").get("value"))
    return value_list


def create_resource_node(graph, operations):
    def merge_resource(resource, resource_tree):
        for parent, children in resource_tree.items():
            for child in children:
                if child + "s" in children:
                    children.remove(child)
                    if child + "s" in resource:
                        resource[child + "s"].extend(resource[child])
                        del resource[child]

    resource = {}
    resource_tree = defaultdict(set)

    for operation in sorted(operations, key=lambda x: len(x.path.__repr__().split("/"))):
        path = operation.path.__repr__()
        split_path = path.split("/")
        if "{" in split_path[-1]:
            resource_name = split_path[-2]
        else:
            resource_name = split_path[-1]
        if resource_name not in resource:
            resource[resource_name] = []
        resource[resource_name].append(operation.__repr__())

        for previous_resource in resource.keys():
            if previous_resource in split_path and previous_resource != resource_name:
                resource_tree[previous_resource].add(resource_name)

    merge_resource(resource, resource_tree)
    for resource, operations in resource.items():
        resource_node = Node("SystemResource", name=resource)
        graph.merge(resource_node, "SystemResource", "name")
        for operation in operations:
            op_node = graph.nodes.match("Operation", name=operation).first()
            graph.create(Relationship(resource_node, "has_operation", op_node))

    for parent, children in resource_tree.items():
        parent_node = graph.nodes.match("SystemResource", name=parent).first()
        for child in children:
            child_node = graph.nodes.match("SystemResource", name=child).first()
            graph.create(Relationship(parent_node, "has_child_resource", child_node))


if __name__ == '__main__':
    # graph = connect_to_db()
    operations = extract_swagger(file_path)
    with open(test_case_path, "r") as file:
        test_cases = json.load(file)
    # delete_all(graph)
    # create_operation_nodes(graph, operations)
    # create_nodes_and_relations_related_to_factors(graph, operations)
    # create_nodes_and_relations_related_to_response_templates(graph, operations)
    # create_resource_node(graph, operations)
    # create_nodes_and_relations_related_to_testcases(graph, operations, test_cases)
    # create_response_assignment(graph, operations)
    # for operation in operations:
    #     possible_value = get_response_value(operation, "response.id")
    #     print(operation, possible_value)
