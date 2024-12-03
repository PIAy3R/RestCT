from collections import defaultdict

import json
from loguru import logger
from py2neo import Graph, Node, Relationship
from tqdm import tqdm

from src.config import Config
from src.swagger import SwaggerParser


class MyGraph:
    def __init__(self, db_name, username, password, swagger_path):
        self.graph = Graph("bolt://localhost:7687", auth=(username, password), name=db_name)

        self.operations = self.extract_swagger(swagger_path)

    def initialize(self):
        """
        Initialize the graph using the information from the swagger file
        """
        logger.info("Initializing the graph")
        logger.debug("Deleting all nodes and relationships")
        self.delete_all()
        logger.debug("Creating nodes and relationships")
        self.create_operation_nodes()
        self.create_nodes_and_relations_related_to_factors()
        self.create_nodes_and_relations_related_to_response_templates()
        self.create_resource_node()

    @staticmethod
    def extract_swagger(swagger_path):
        config = Config()
        config.swagger = swagger_path
        parser = SwaggerParser(config)
        operations = parser.extract()
        return operations

    def delete_all(self):
        """
        Delete all nodes and relationships in the database
        """
        cypher_delete_all = "match (n) detach delete n"
        self.graph.run(cypher_delete_all)

    def create_operation_nodes(self):
        """
        Create nodes for operations
        """
        for operation in tqdm(self.operations, desc="Creating Operation Nodes"):
            op_node = Node("Operation", name=operation.__repr__(), method=operation.verb.value,
                           path=operation.path.__repr__(),
                           description=operation.description)

            self.graph.merge(op_node, "Operation", "name")

    def create_nodes_and_relations_related_to_factors(self):
        """
        Create nodes for factors and their relationships with operations
        """
        for operation in tqdm(self.operations, desc=f"Creating Factor Nodes for Operations"):
            for parameter in operation.parameters:
                for factor in parameter.factor.get_leaves():
                    if factor.description is None:
                        description = ""
                    else:
                        description = factor.description
                    factor_node = Node("Factor", name=factor.get_global_name, required=factor.required,
                                       description=description, format=factor.format,
                                       location=parameter.__class__.__name__, type=factor.__class__.__name__)
                    self.graph.merge(factor_node, "Factor", ("name", "required", "description", "location", "type"))
                    op_node = self.graph.nodes.match("Operation", name=operation.__repr__()).first()
                    self.graph.create(Relationship(op_node, "has_factor", factor_node))

    def create_nodes_and_relations_related_to_response_templates(self):
        """
        Create nodes for response templates and their relationships with operations
        """
        for operation in tqdm(self.operations, desc="Creating Response Nodes for Operations"):
            for response in operation.responses:
                if len(response.contents) > 0:
                    content_type = response.contents[0][0]
                    data_type = response.contents[0][1].__class__.__name__
                else:
                    content_type = ""
                    data_type = ""
                response_node = Node("ResponseTemplate", status_code=response.status_code,
                                     description=response.description,
                                     content_type=content_type, data_type=data_type)
                self.graph.merge(response_node, "ResponseTemplate",
                                 ("status_code", "description", "content_type", "data_type"))
                op_node = self.graph.nodes.match("Operation", name=operation.__repr__()).first()
                self.graph.create(Relationship(op_node, "has_response_template", response_node))
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
                            self.graph.create(response_factor_node)
                            self.graph.create(Relationship(response_node, "has_factor", response_factor_node))

    def create_resource_node(self):
        """
        Create nodes for resources and their relationships with operations
        """

        resource = {}
        resource_tree = defaultdict(set)

        for operation in sorted(self.operations, key=lambda x: len(x.path.__repr__().split("/"))):
            path = operation.path.__repr__()
            split_path = path.split("/")
            if "{" in split_path[-1]:
                for index, item in enumerate(reversed(split_path)):
                    if "{" not in item:
                        resource_name = item
                        break
            else:
                resource_name = split_path[-1]
            if resource_name not in resource:
                resource[resource_name] = []
            resource[resource_name].append(operation.__repr__())

            for item in reversed(split_path):
                if item in resource.keys() and item != resource_name:
                    resource_tree[item].add(resource_name)
                    break

        for resource, operations in resource.items():
            resource_node = Node("SystemResource", name=resource)
            self.graph.merge(resource_node, "SystemResource", "name")
            for operation in operations:
                op_node = self.graph.nodes.match("Operation", name=operation).first()
                self.graph.create(Relationship(resource_node, "has_operation", op_node))

        for parent, children in resource_tree.items():
            parent_node = self.graph.nodes.match("SystemResource", name=parent).first()
            for child in children:
                child_node = self.graph.nodes.match("SystemResource", name=child).first()
                self.graph.create(Relationship(parent_node, "has_child_resource", child_node))

    def create_nodes_and_relations_related_to_testcases(self, cases):
        """
        Create nodes for testcases and their relationships with operations
        """
        for operation in tqdm(self.operations, desc="Creating Testcases for Operations"):
            op_cases = cases[operation.__repr__()]
            for info in op_cases:
                case = info[0]
                response_text = info[1]
                status_code = info[2]
                if int(status_code) // 100 == 2 or int(status_code) // 100 == 5:

                    op_node = self.graph.nodes.match("Operation", name=operation.__repr__()).first()
                    # total_cases
                    match_all_cases = "MATCH (o:Operation{{{}}})-[r:has_case]->(c:Testcase) RETURN count(c)".format(
                        ":".join(["name", "'" + operation.__repr__() + "'"]))
                    id = int(self.graph.run(match_all_cases).data()[0]["count(c)"]) + 1
                    case_node = Node("Testcase", id=id, status_code=status_code, operation=operation.__repr__())

                    self.graph.merge(case_node, "Testcase", ("id", "operation"))
                    response_node = Node("Response", text=json.dumps(response_text), status_code=status_code)
                    self.graph.create(response_node)
                    self.graph.create(Relationship(op_node, "has_case", case_node))
                    self.graph.create(Relationship(case_node, "has_response", response_node))
                    for factor in operation.get_leaf_factors():
                        if factor.get_global_name in case:
                            find_node = "MATCH (o:Operation{{name:'{}'}})-[r1: has_factor]->(f:Factor{{name:'{}'}}) return f".format(
                                operation.__repr__(), factor.get_global_name)
                            matched = self.graph.run(find_node).data()
                            location = matched[0]["f"].get("location")
                            assignment_node = Node("Assignment", name=factor.get_global_name, location=location)
                            value = case[factor.get_global_name]
                            value_node = Node("Value", value=str(value),
                                              type=factor.__class__.__name__.replace("Factor", "").lower())
                            self.graph.create(assignment_node)
                            self.graph.merge(value_node, "Value", "value")
                            self.graph.create(Relationship(assignment_node, "has_value", value_node))
                            self.graph.create(Relationship(case_node, "has_assignment", assignment_node))

    @staticmethod
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

    def get_response_value(self, operation, factor_name):
        """
        Get the value of a factor from a response after creating in the graph
        """
        match = "MATCH(n: Operation{{name:'{}'}})-[r1: has_case]->(c:Testcase)-[r2: has_response]->(r:Response)-[r3: has_assignment]->(a:Assignment{{name:'{}'}})-[r4: has_value]->(v:Value) RETURN n, r1, c, r2, r, r3, a, r4, v".format(
            operation.__repr__(), factor_name)
        matched = self.graph.run(match).data()
        value_list = []
        for chain in matched:
            value_list.append(chain.get("v").get("value"))
        return value_list

    def create_test_resource(self):
        """
        Create test resources
        """
        for operation in tqdm(self.operations, desc="Creating Resources"):
            if operation.verb.value == "post":
                # same level
                match_factors = "MATCH (o:Operation{{name:'{}'}})-[:has_response_template]->(r:ResponseTemplate)-[:has_factor]->(f:Factor) RETURN r, f".format(
                    operation.__repr__())
                match_resources = "MATCH (s:SystemResource)-[r:has_operation]->(o:Operation{{name:'{}'}}) RETURN s".format(
                    operation.__repr__())
                match_response = "MATCH (o:Operation{{name:'{}'}})-[:has_case]->(c:Testcase)-[:has_response]->(r:Response) RETURN c, r".format(
                    operation.__repr__())
                response_template = self.graph.run(match_factors).data()
                resource_node = self.graph.run(match_resources).data()[0]["s"]
                case_response_pairs = [(d.get("c"), d.get("r")) for d in self.graph.run(match_response).data()]
                for case_response in case_response_pairs:
                    response_factors = []
                    case_node = case_response[0]
                    response_node = case_response[1]

                    if int(response_node.get("status_code")) // 100 == 2:

                        test_resource_node = Node("TestResource", id=case_node.get("id"), status="existed",
                                                  resource=resource_node.get("name"))
                        self.graph.merge(test_resource_node, "TestResource", ("id", "status", "resource"))
                        self.graph.create(Relationship(resource_node, "has_resource", test_resource_node))

                        for template_factor in response_template:
                            template = template_factor.get("r")
                            if template.get("status_code") == response_node.get("status_code"):
                                response_factors.append(template_factor.get("f"))

                        response_text = response_node.get("text")
                        response_json = json.loads(response_text)

                        for factor in response_factors:
                            value = self.get_factor_value(response_json, factor)
                            if value is not None:
                                property_node = Node("ResourceProperty", name=factor.get("name"))
                                value_node = Node("Value", value=str(value),
                                                  type=factor.get("type").replace("Factor", "").lower())
                                self.graph.create(property_node)
                                self.graph.merge(value_node, "Value", "value")
                                self.graph.create(Relationship(test_resource_node, "has_property", property_node))
                                self.graph.create(Relationship(property_node, "has_value", value_node))
                                self.graph.create(Relationship(case_node, "operated", test_resource_node))

            elif operation.verb.value == "delete":
                pass

    def test(self):
        for operation in self.operations:
            # if operation.verb.value == "post":
            #     match_sys_resource = "MATCH (s:SystemResource)-[r:has_operation]->(o:Operation{{name:'{}'}}) RETURN s".format(
            #         operation.__repr__())
            #     match_test_resources = "MATCH (o:Operation{{name:'{}'}})-[:has_case]->(c:Testcase)-[:operated]->(r:TestResource) RETURN c, r".format(
            #         operation.__repr__())
            #     sys_resource = self.graph.run(match_sys_resource).data()[0]["s"]
            #     case_resource_pairs = [(d.get("c"), d.get("r")) for d in self.graph.run(match_test_resources).data()]
            #
            #     match_parent_sys_resource = "MATCH (s:SystemResource)-[:has_child_resource]->(c:SystemResource{{name:'{}'}}) RETURN s".format(
            #         sys_resource.get("name"))
            #     parent_sys_resource_list = self.graph.run(match_parent_sys_resource).data()
            #     if len(parent_sys_resource_list) > 0:
            #         parent_sys_resource = parent_sys_resource_list[0]["s"]
            #     else:
            #         continue
            #
            #     for case_resource in case_resource_pairs:
            #         case_node = case_resource[0]
            #         resource_node = case_resource[1]
            #         match_property = """
            #         MATCH (c:Testcase{{id:{}, operation:'{}'}})-[:has_assignment]->(a:Assignment{{location:'{}'}})-[:has_value]->(v:Value)
            #         WITH v
            #         MATCH (s:SystemResource{{name:'{}'}})-[:has_resource]->(t:TestResource)-[:has_property]->(p:ResourceProperty)-[:has_value]->(v:Value)
            #         RETURN s,t, p, v
            #         """.format(case_node.get("id"), case_node.get("operation"), "PathParam", parent_sys_resource.get("name"))
            #         data = self.graph.run(match_property).data()[0]
            #         parent_resource_node = data.get("t")
            #         self.graph.create(Relationship(parent_resource_node, "followed_by", resource_node))

            if operation.verb.value == "delete":
                match_test_resources = """
                MATCH (s:SystemResource)-[:has_operation]->(o:Operation{{name:'{}'}}) WITH s
                MATCH (s)-[:has_resource]->(r:TestResource) RETURN r
                """.format(operation.__repr__())
                resources = [d.get("r") for d in self.graph.run(match_test_resources).data()]
                if len(resources) > 0:
                    match_cases = """
                    MATCH (o:Operation{{name:'{}'}})-[:has_case]->(c:Testcase) RETURN c
                    """.format(operation.__repr__())
                    cases = [d.get("c") for d in self.graph.run(match_cases).data()]
                    for c in cases:
                        match_case_resource = """
                        MATCH (c:Testcase{{id:{}, operation:'{}'}})-[:has_assignment]->(a:Assignment{{location:'{}'}})-[:has_value]->(v:Value) 
                        WITH v
                        MATCH (o:Operation{{name: '{}'}})-[:has_case]->(c:Testcase)-[:has_assignment]->(a:Assignment{{location:'{}'}})-[:has_value]->(v:Value)
                        WITH c
                        MATCH (c)-[:operated]->(r:TestResource) RETURN r
                        """.format(c.get("id"), operation.__repr__(), "PathParam",
                                   operation.__repr__().replace("delete:", "post:"), "PathParam")
                        print(self.graph.run(match_case_resource).data())
                # for case_resource in case_resource_pairs:
                #     case_node = case_resource[0]
                #     resource_node = case_resource[1]
                #     match_resource = """
                #     MATCH (c:Testcase{{id:{}, operation:'{}'}})-[:has_assignment]->(a:Assignment{{location:'{}'}})-[:has_value]->(v:Value)
                #     WITH v
                #     MATCH (s:SystemResource{{path:'{}', method:'post'}})-[:has_resource]->(t:TestResource)-[:has_property]->(p:ResourceProperty)-[:has_value]->(v:Value)
                #     RETURN t, v
                #     """.format(case_node.get("id"), case_node.get("operation"), "PathParam", operation.path.__repr__())
                #     data = self.graph.run(match_resource).data()[0]
                #     print(data)




if __name__ == '__main__':
    file_path = "/Users/naariah/Documents/Python_Codes/api-suts/specifications/v3/gitlab-branch-13.json"
    test_case_path = "/Users/naariah/Documents/Python_Codes/RestCT/out/test_data/case_response_1.json"
    graph = MyGraph("rest", "pzy", "12345678", file_path)
    with open(test_case_path, "r") as file:
        test_cases = json.load(file)
    # graph.initialize()
    # graph.create_nodes_and_relations_related_to_testcases(test_cases)
    # graph.create_test_resource()

    graph.test()
