import csv
from pathlib import Path
from typing import Optional, Dict, List, Set
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD, SH, RDFS


class CSVToSHACL:
    """Class to transform CSV files to SHACL shapes."""
    
    def __init__(self, base_uri: str = "http://example.org/"):
        """Initialize the transformer with namespaces and RDF graph.
        
        Args:
            base_uri: Base URI for resources (default: "http://example.org/")
        """
        self.g = Graph()
        self.base_uri = base_uri.rstrip('/') + '/'  
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
        """Add a property shape to the node shape with enhanced constraints.
        
        Args:
            node_shape: URI of the node shape
            property_name: Name of the property (dots replaced with underscores)
            property_type: XSD datatype for the property
            values: Sample values for the property
        """
        # Replace dots with underscores in property name
        safe_property_name = property_name.replace('.', '_')
        property_uri = URIRef(f"{self.base_uri}{safe_property_name}")
        
 
        self.g.add((property_uri, RDF.type, SH.PropertyShape))
        self.g.add((property_uri, SH.path, property_uri))
        self.g.add((property_uri, SH.datatype, property_type))
        self.g.add((property_uri, SH.name, Literal(property_name)))
        
        # # Add min/max count based on null values
        # null_count = sum(1 for v in values if not v.strip())
        # if null_count == 0:
        #     self.g.add((property_uri, SH.minCount, Literal(1)))
        
        # Add maxLength for strings
        if property_type == XSD.string:
            max_len = max(len(v) for v in values if v.strip())
            self.g.add((property_uri, SH.maxLength, Literal(max_len)))
        
        # Add value constraints for small sets of distinct values
        distinct_values = {v.strip() for v in values if v.strip()}
        if 1 < len(distinct_values) <= 10:
            # Add sh:in for enumerations
            value_list = URIRef(f"{property_uri}_values")
            self.g.add((value_list, RDF.type, RDF.List))
            current = value_list
            for i, val in enumerate(distinct_values):
                lit = Literal(val, datatype=property_type)
                self.g.add((current, RDF.first, lit))
                if i < len(distinct_values) - 1:
                    next_node = URIRef(f"{property_uri}_values_{i}")
                    self.g.add((current, RDF.rest, next_node))
                    current = next_node
                else:
                    self.g.add((current, RDF.rest, RDF.nil))
            self.g.add((property_uri, SH["in"], value_list))
        
        # Add numeric range constraints
        if property_type in (XSD.integer, XSD.decimal):
            numeric_values = [float(v) for v in values if v.strip()]
            if numeric_values:
                self.g.add((property_uri, SH.minInclusive, Literal(min(numeric_values))))
                self.g.add((property_uri, SH.maxInclusive, Literal(max(numeric_values))))
      
        self.g.add((node_shape, SH.property, property_uri))
    
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
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
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
                    values = [row[column] for row in rows if row[column] is not None]
                    prop_type = self._guess_property_type(values)
                    self._add_property_shape(node_shape_uri, column, prop_type, values)
                
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
    transformer = CSVToSHACL(base_uri="http://i14y.admin.ch/ns#")
    
    input_csv = "example/iris.csv"
    output_ttl = "example/shapes.ttl"
    node_shape_name = "Iris" # Optional - will use filename if None
    
    if transformer.transform_csv_to_shacl(input_csv, node_shape_name):
        transformer.save_shacl(output_ttl)
    else:
        print("Failed to transform CSV to SHACL")
