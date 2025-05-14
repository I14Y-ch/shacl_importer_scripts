from rdflib import Graph
import json

def ttl_to_jsonld_strict_prefixes(ttl_file_path, jsonld_file_path):
    # Load the TTL file with UTF-8 encoding
    g = Graph()
    with open(ttl_file_path, 'r', encoding='utf-8') as ttl_file:
        g.parse(data=ttl_file.read(), format='turtle')

    # Manually extract ONLY the prefixes from the TTL file
    declared_prefixes = {}
    for line in open(ttl_file_path, 'r', encoding='utf-8'):
        line = line.strip()
        if line.startswith("@prefix"):
            parts = line.split()
            prefix = parts[1][:-1]  # Remove trailing ':'
            uri = parts[2][1:-2]    # Remove '<' and '>.'
            declared_prefixes[prefix] = uri

    # Generate JSON-LD with forced prefix usage
    jsonld_data = g.serialize(
        format='json-ld',
        context=declared_prefixes,
        indent=4,
        ensure_ascii=False,
        use_prefixes=True  # This forces prefix usage in the output
    )

    # Save with UTF-8 encoding
    with open(jsonld_file_path, 'w', encoding='utf-8') as f:
        f.write(jsonld_data)

    print(f"Conversion complete! Output saved to {jsonld_file_path}")



# Example usage
if __name__ == "__main__":
    input_ttl = "C:/Users/U80877014/Documents/Structure/shacl_importer_scripts/import_template/json_template/example/structure_with_two_classes.ttl"  # Replace with your input TTL file
    output_jsonld = "structure_with_two_classes.json"  # Replace with desired output JSON-LD file
    ttl_to_jsonld_strict_prefixes(input_ttl, output_jsonld)