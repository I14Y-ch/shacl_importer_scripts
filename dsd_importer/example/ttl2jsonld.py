from rdflib import Graph, URIRef
import json
from rdflib.namespace import NamespaceManager

def ttl_to_jsonld_strict_prefixes(ttl_file_path, jsonld_file_path):
    # Load the TTL file with UTF-8 encoding
    g = Graph()
    with open(ttl_file_path, 'r', encoding='utf-8') as ttl_file:
        g.parse(data=ttl_file.read(), format='turtle')

    # Manually extract the prefixes from the TTL file
    declared_prefixes = {}
    for prefix, uri in g.namespaces():
        declared_prefixes[str(prefix)] = str(uri) if prefix else None

    # Remove any None keys (default namespace)
    declared_prefixes = {k: v for k, v in declared_prefixes.items() if k}

    # Generate initial JSON-LD
    jsonld_str = g.serialize(
        format='json-ld',
        context=declared_prefixes,
        indent=4,
        ensure_ascii=False
    )

    # Parse the JSON-LD to modify it
    jsonld_data = json.loads(jsonld_str)

    # Function to shorten URIs using prefixes
    def shorten_uri(uri, prefixes):
        for prefix, base_uri in prefixes.items():
            if uri.startswith(base_uri):
                return f"{prefix}:{uri[len(base_uri):]}"
        return uri

    # Process all URIs in the JSON-LD to use prefixes
    def process_value(value, prefixes):
        if isinstance(value, dict):
            if '@id' in value:
                value['@id'] = shorten_uri(value['@id'], prefixes)
            return value
        elif isinstance(value, str):
            return shorten_uri(value, prefixes)
        return value

    # Process the entire JSON-LD structure
    if '@graph' in jsonld_data:
        for item in jsonld_data['@graph']:
            for key, value in list(item.items()):
                if isinstance(value, dict):
                    item[key] = process_value(value, declared_prefixes)
                elif isinstance(value, list):
                    item[key] = [process_value(v, declared_prefixes) for v in value]
                elif isinstance(value, str) and key != '@type':
                    item[key] = process_value(value, declared_prefixes)

    # Save with UTF-8 encoding
    with open(jsonld_file_path, 'w', encoding='utf-8') as f:
        json.dump(jsonld_data, f, indent=4, ensure_ascii=False)

    print(f"Conversion complete! Output saved to {jsonld_file_path}")

# Example usage
if __name__ == "__main__":
    input_ttl = "C:/Users/U80877014/Documents/Structure/shacl_importer_scripts/dsd_importer/example/ch_admin_beta_id.ttl"  # Replace with your input TTL file
    output_jsonld = "C:/Users/U80877014/Documents/Structure/shacl_importer_scripts/dsd_importer/example/ch_admin_beta_id.json"  # Replace with desired output JSON-LD file
    ttl_to_jsonld_strict_prefixes(input_ttl, output_jsonld)