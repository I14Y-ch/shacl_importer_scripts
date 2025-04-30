import csv
from pathlib import Path
from typing import Optional, Dict, List, Set
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD, SH, RDFS
from urllib.parse import quote


class CSVToSHACL:
    """Class to transform CSV files to SHACL shapes."""
    
    def __init__(self, base_uri: str = "http://example.org/", default_lang: str = None):
        """Initialize the transformer with namespaces and RDF graph.
        
        Args:
            base_uri: Base URI for resources (default: "http://example.org/")
            default_lang: Default language tag for string literals (e.g., "de")
        """
        self.g = Graph()
        self.base_uri = base_uri.rstrip('/') + '/'
        self.default_lang = default_lang
        self._initialize_namespaces()
        
    def _initialize_namespaces(self) -> None:
        """Set up all required namespaces and bind them to the graph."""
        self.sh = Namespace("http://www.w3.org/ns/shacl#")
        self.ex = Namespace(self.base_uri)
        
        self.g.bind("sh", SH)
        self.g.bind("i14y", self.ex)
    
    @staticmethod
    def _guess_property_type(values: List[str]) -> URIRef:
        """Guess the XSD datatype based on sample values.
        
        Args:
            values: List of string values from the CSV column
            
        Returns:
            Appropriate XSD datatype URI
        """
        if not values:
            return XSD.string
            
        sample = values[0].strip() if values[0] else ""
        
        # Check for integer
        if all(v.strip().isdigit() for v in values if v.strip()):
            return XSD.integer
            
        # Check for decimal
        decimal_count = 0
        for v in values:
            if v.strip():
                try:
                    float(v)
                    decimal_count += 1
                except ValueError:
                    pass
        if decimal_count == len([v for v in values if v.strip()]):
            return XSD.decimal
            
        # Check for boolean
        bool_values = {'true', 'false', 't', 'f', 'yes', 'no', '1', '0'}
        if all(v.strip().lower() in bool_values for v in values if v.strip()):
            return XSD.boolean
            
        # Check for date
        date_count = 0
        for v in values:
            if v.strip():
                parts = v.split('-')
                if len(parts) == 3 and len(parts[0]) == 4 and parts[0].isdigit():
                    date_count += 1
        if date_count == len([v for v in values if v.strip()]):
            return XSD.date
            
        return XSD.string

    def _add_property_shape(self, node_shape: URIRef, property_name: str, 
                        property_type: URIRef, values: List[str]) -> None:
        """Add a property shape to the node shape with enhanced constraints."""
        # Create a safe property name
        safe_property_name = (
            property_name.strip()
            .replace(' ', '_')
            .replace('.', '_')
        )
        property_uri = URIRef(f"{self.base_uri}{safe_property_name}")
        
        self.g.add((property_uri, RDF.type, SH.PropertyShape))
        self.g.add((property_uri, SH.path, property_uri))
        self.g.add((property_uri, SH.datatype, property_type))
        
        # Add language tag to name if default language is set
        if self.default_lang:
            self.g.add((property_uri, SH.name, Literal(property_name, lang=self.default_lang)))
        else:
            self.g.add((property_uri, SH.name, Literal(property_name)))
        
        # Handle string values with language tags
        if property_type == XSD.string and self.default_lang:
            distinct_values = {v.strip() for v in values if v.strip()}
            if 1 < len(distinct_values) <= 10:
                value_list = URIRef(f"{property_uri}_values")
                self.g.add((value_list, RDF.type, RDF.List))
                current = value_list
                for i, val in enumerate(distinct_values):
                    lit = Literal(val, lang=self.default_lang)  # Add language tag here
                    self.g.add((current, RDF.first, lit))
                    if i < len(distinct_values) - 1:
                        next_node = URIRef(f"{property_uri}_values_{i}")
                        self.g.add((current, RDF.rest, next_node))
                        current = next_node
                    else:
                        self.g.add((current, RDF.rest, RDF.nil))
                self.g.add((property_uri, SH["in"], value_list))
        
    def transform_csv_to_shacl(self, csv_file: str, 
                            node_shape_name: Optional[str] = None) -> bool:
        """Transform a CSV file to SHACL.
        
        Args:
            csv_file: Path to the CSV file
            node_shape_name: Optional name for the NodeShape (defaults to filename)
            
        Returns:
            True if transformation succeeded, False otherwise
        """
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:  # Note: utf-8-sig to handle BOM
                reader = csv.DictReader(f, delimiter=';')  # Explicitly specify semicolon delimiter
                
                rows = list(reader)
                
                if not rows:
                    print("CSV file is empty")
                    return False
            
                if node_shape_name is None:
                    node_shape_name = Path(csv_file).stem  
                node_shape_uri = URIRef(f"{self.base_uri}{node_shape_name}Shape")
                self.g.add((node_shape_uri, RDF.type, SH.NodeShape))
                self.g.add((node_shape_uri, SH.name, Literal(node_shape_name)))
                
                # Add closed shape (only defined properties allowed)
                self.g.add((node_shape_uri, SH.closed, Literal(False)))
                
                for column in reader.fieldnames:
                    # Clean column name by removing BOM if present
                    clean_column = column.replace('\ufeff', '').strip()
                    values = [row[clean_column] for row in rows if clean_column in row and row[clean_column] is not None]
                    prop_type = self._guess_property_type(values)
                    self._add_property_shape(node_shape_uri, clean_column, prop_type, values)
                
                return True
                
        except Exception as e:
            print(f"Error processing CSV file: {e}")
            return False
    
    def save_shacl(self, output_file: str) -> None:
        """Save the SHACL graph to a Turtle file.
        
        Args:
            output_file: Path to the output Turtle file
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.g.serialize(format="turtle"))
        print(f"SHACL shape saved to {output_file}")


if __name__ == "__main__":
    base_uri = "http://i14y.admin.ch/ns#"
    
    transformer = CSVToSHACL(base_uri, default_lang="de" )
    
    input_csv = "c:/Users/U80877014/Documents/Structure/shacl_importer/csv_importer/example_csv/12070.csv"
    output_ttl = "c:/Users/U80877014/Documents/Structure/shacl_importer/csv_importer/example_csv/shapes.ttl"

    node_shape_name = None # Optional - will use filename if None else you can state the file name "file_name"
    

    if transformer.transform_csv_to_shacl(input_csv, node_shape_name):
        transformer.save_shacl(output_ttl)
    else:
        print("Failed to transform CSV to SHACL")
