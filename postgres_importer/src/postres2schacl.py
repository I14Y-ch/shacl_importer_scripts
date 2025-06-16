import psycopg2
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS

import os
from dotenv import load_dotenv
load_dotenv()

# Define namespaces
SH = Namespace("http://www.w3.org/ns/shacl#")
DB = Namespace("http://example.org/database#")
DCT = Namespace("http://purl.org/dc/terms/")

def connect_to_postgres(host, port, database, user, password):
    """Connect to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    return conn

def fetch_schema_info(conn):
    """Fetch schema information from the PostgreSQL database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'data'
        ORDER BY table_name, ordinal_position;
    """)
    return cursor.fetchall()

def generate_shacl(schema_info):
    """Generate SHACL shapes from the database schema."""
    g = Graph()
    g.bind("sh", SH)
    g.bind("db", DB)
    g.bind("dct", DCT)

    tables = {}
    for table_name, column_name, data_type, is_nullable in schema_info:
        if table_name not in tables:
            tables[table_name] = DB[table_name]
            g.add((tables[table_name], RDF.type, SH.NodeShape))
            g.add((tables[table_name], SH.targetClass, DB[table_name]))
            g.add((tables[table_name], SH.closed, Literal(True)))

        prop_shape = DB[f"{table_name}/{column_name}"]
        g.add((prop_shape, RDF.type, SH.PropertyShape))
        g.add((prop_shape, SH.path, DB[column_name]))
        g.add((prop_shape, SH.name, Literal(column_name, lang="en")))
        g.add((prop_shape, SH.datatype, XSD[data_type] if data_type in XSD else Literal(data_type)))
        g.add((prop_shape, SH.minCount, Literal(0 if is_nullable == "YES" else 1, datatype=XSD.integer)))

        g.add((tables[table_name], SH.property, prop_shape))

    return g

def save_shacl(g, output_file):
    """Save the SHACL graph to an RDF file."""
    g.serialize(destination=output_file, format="turtle")

def postgres_to_shacl(host, port, database, user, password, output_file):
    """Convert a PostgreSQL database schema to a SHACL RDF file."""
    conn = connect_to_postgres(host, port, database, user, password)
    schema_info = fetch_schema_info(conn)
    conn.close()

    shacl_graph = generate_shacl(schema_info)
    save_shacl(shacl_graph, output_file)

# Example usage
#postgres_to_shacl("localhost", 5432, "TEST", "postgres", os.environ.get("password"), "postgres_importer/example/output.ttl")