"""Test Memory class in jena."""

import unittest
import os
import time
import docker
import requests
from SPARQLWrapper import SPARQLWrapper, POST, JSON, TURTLE

from humemai.utils.docker import (
    run_jena_container,
    stop_jena_container,
    start_jena_container,
    create_db_jena,
    remove_db_jena,
    remove_jena_container,
    wait_for_fuseki,
)


class TestMemory(unittest.TestCase):
    def test_flow(self) -> None:
        client = docker.from_env()
        try:
            remove_jena_container(client, "foo")
        except:
            pass

        try:
            run_jena_container(client, "foo")
        except:
            start_jena_container(client, "foo")

        wait_for_fuseki()

        try:
            create_db_jena("db")
        except:
            remove_db_jena("db")
            create_db_jena("db")

        sparql = SPARQLWrapper("http://localhost:3030/db/update")

        # Set the credentials (assuming default username 'admin' and password 'your_password')
        sparql.setCredentials("admin", "admin")

        # Define a larger SPARQL INSERT query for RDF* data with more entities and metadata
        insert_rdf_star = """
            INSERT DATA {
                # Relationships between people
                <http://example.org/Alice> <http://example.org/knows> <http://example.org/Bob> .
                << <http://example.org/Alice> <http://example.org/knows> <http://example.org/Bob> >> 
                    <http://example.org/certainty> "high" ;
                    <http://example.org/startedAt> "2021-01-01"^^<http://www.w3.org/2001/XMLSchema#date> ;
                    <http://example.org/friendshipScore> "95"^^<http://www.w3.org/2001/XMLSchema#integer> .

                <http://example.org/Alice> <http://example.org/worksWith> <http://example.org/Charlie> .
                << <http://example.org/Alice> <http://example.org/worksWith> <http://example.org/Charlie> >> 
                    <http://example.org/certainty> "medium" ;
                    <http://example.org/startedAt> "2022-03-15"^^<http://www.w3.org/2001/XMLSchema#date> ;
                    <http://example.org/workScore> "85"^^<http://www.w3.org/2001/XMLSchema#integer> .

                <http://example.org/Bob> <http://example.org/knows> <http://example.org/Charlie> .
                << <http://example.org/Bob> <http://example.org/knows> <http://example.org/Charlie> >> 
                    <http://example.org/certainty> "low" ;
                    <http://example.org/startedAt> "2020-06-20"^^<http://www.w3.org/2001/XMLSchema#date> ;
                    <http://example.org/friendshipScore> "70"^^<http://www.w3.org/2001/XMLSchema#integer> .

                # Adding more metadata about the relationships
                <http://example.org/Charlie> <http://example.org/knows> <http://example.org/David> .
                << <http://example.org/Charlie> <http://example.org/knows> <http://example.org/David> >> 
                    <http://example.org/certainty> "very high" ;
                    <http://example.org/startedAt> "2019-09-05"^^<http://www.w3.org/2001/XMLSchema#date> ;
                    <http://example.org/friendshipScore> "100"^^<http://www.w3.org/2001/XMLSchema#integer> .

                <http://example.org/David> <http://example.org/worksWith> <http://example.org/Alice> .
                << <http://example.org/David> <http://example.org/worksWith> <http://example.org/Alice> >> 
                    <http://example.org/certainty> "high" ;
                    <http://example.org/startedAt> "2018-11-11"^^<http://www.w3.org/2001/XMLSchema#date> ;
                    <http://example.org/workScore> "90"^^<http://www.w3.org/2001/XMLSchema#integer> .

                # Additional metadata on people themselves
                <http://example.org/Alice> <http://example.org/age> "30"^^<http://www.w3.org/2001/XMLSchema#integer> .
                <http://example.org/Bob> <http://example.org/age> "35"^^<http://www.w3.org/2001/XMLSchema#integer> .
                <http://example.org/Charlie> <http://example.org/age> "28"^^<http://www.w3.org/2001/XMLSchema#integer> .
                <http://example.org/David> <http://example.org/age> "40"^^<http://www.w3.org/2001/XMLSchema#integer> .

                # Adding occupations
                <http://example.org/Alice> <http://example.org/occupation> "Engineer" .
                <http://example.org/Bob> <http://example.org/occupation> "Artist" .
                <http://example.org/Charlie> <http://example.org/occupation> "Data Scientist" .
                <http://example.org/David> <http://example.org/occupation> "Manager" .
            }
        """

        # Set the query method to POST (for updates)
        sparql.setQuery(insert_rdf_star)
        sparql.setMethod(POST)

        # Execute the insert query
        sparql.query()
        print("Larger RDF* dataset inserted successfully!")

        # Set up the SPARQL Query endpoint for the 'ds' dataset
        sparql = SPARQLWrapper("http://localhost:3030/db/sparql")

        # Define the SPARQL query to retrieve RDF* data
        select_rdf_star = """
            SELECT ?s ?p ?o ?certainty WHERE {
            ?s ?p ?o .
            << ?s ?p ?o >> <http://example.org/certainty> ?certainty .
            }
        """

        # Set the query method and return format
        sparql.setQuery(select_rdf_star)
        sparql.setReturnFormat(JSON)

        # Execute the query and print results
        results = sparql.query().convert()

        for result in results["results"]["bindings"]:
            print(
                f"Subject: {result['s']['value']}, Predicate: {result['p']['value']}, Object: {result['o']['value']}, Certainty: {result['certainty']['value']}"
            )

        sparql = SPARQLWrapper("http://localhost:3030/db/sparql")

        # Define the SPARQL query to get all standard triples (no RDF-star)
        select_standard_triples = """
            SELECT ?s ?p ?o WHERE {
            ?s ?p ?o .
            }
        """

        # Set the query method and return format
        sparql.setQuery(select_standard_triples)
        sparql.setReturnFormat(JSON)

        # Execute the query and print results
        results = sparql.query().convert()

        # Loop through the results and print each triple
        for result in results["results"]["bindings"]:
            print(
                f"Subject: {result['s']['value']}, Predicate: {result['p']['value']}, Object: {result['o']['value']}"
            )

        # Set up the SPARQL Query endpoint for your dataset
        sparql = SPARQLWrapper("http://localhost:3030/db/sparql")

        # Define the SPARQL CONSTRUCT query to get all triples
        construct_query = """
            CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o . }
        """

        # Set the query method and return format (Turtle)
        sparql.setQuery(construct_query)
        sparql.setReturnFormat(TURTLE)

        # Execute the query and retrieve results in Turtle format
        turtle_data = sparql.query().convert()

        # Write the Turtle data to a file
        with open("example.ttl", "wb") as f:
            f.write(turtle_data)

        print("Data exported as Turtle format.")

        # Set up the SPARQL Query endpoint for the 'foo' dataset
        sparql = SPARQLWrapper("http://localhost:3030/db/update")

        # Set the credentials (assuming default username 'admin' and password 'your_password')
        sparql.setCredentials("admin", "admin")

        # Define the SPARQL query to delete all triples
        delete_all_triples = """
            DELETE WHERE {
            ?s ?p ?o .
            }
        """

        # Set the query method and execute the update
        sparql.setQuery(delete_all_triples)
        sparql.setMethod(POST)  # Since it's an update, use POST
        sparql.query()

        print("All triples have been deleted from the database.")

        # Set up the SPARQL Update endpoint for the 'foo' dataset
        sparql_endpoint = "http://localhost:3030/db/data"

        # Set the headers for the request (important for content type Turtle)
        headers = {"Content-Type": "text/turtle"}

        # Read the Turtle file content
        with open("example.ttl", "r") as file:
            turtle_data = file.read()

        # Perform the POST request to import the Turtle data
        response = requests.post(
            sparql_endpoint, headers=headers, data=turtle_data, auth=("admin", "admin")
        )

        # Check if the import was successful
        if response.status_code == 200:
            print("Turtle file imported successfully!")
        else:
            raise Exception(
                f"Failed to import Turtle file. Status code: {response.status_code}, Response: {response.text}"
            )

        # Delete the file
        os.remove("example.ttl")

        stop_jena_container(client, "foo")
        remove_jena_container(client, "foo")
