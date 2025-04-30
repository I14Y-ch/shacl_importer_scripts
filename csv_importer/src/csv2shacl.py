import csv
from pathlib import Path
from typing import Optional, List
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD, SH

class CSVToSHACL:
    """Enhanced CSV to SHACL transformer with better year detection and numeric constraints."""
    
    # Common year column names in multiple languages
    YEAR_KEYWORDS = {
        'en': ['year', 'yr'],
        'de': ['jahr', 'jahrgang'],
        'fr': ['année', 'an'],
        'it': ['anno', 'annata']
    }
    
    def __init__(self, base_uri: str = "http://example.org/", default_lang: str = None):
        self.g = Graph()
        self.base_uri = base_uri.rstrip('/') + '/'
        self.default_lang = default_lang
        self.sh = SH
        self.g.bind("sh", SH)
        self.ex = Namespace(self.base_uri)
        self.g.bind("i14y", self.ex)

    def _is_year_column(self, column_name: str) -> bool:
        """Check if column name indicates it contains year values."""
        lower_name = column_name.lower()
        for lang, keywords in self.YEAR_KEYWORDS.items():
            if any(keyword in lower_name for keyword in keywords):
                return True
        return False
    
    def _guess_property_type(self, values: List[str], column_name: str) -> URIRef:
        """Enhanced type guessing with special handling for year columns."""
        if not values:
            return XSD.string
            
        sample = values[0].strip() if values[0] else ""
        

        if self._is_year_column(column_name):
            # Check if it's a valid date (YYYY or YYYY-MM-DD format)
            if (len(sample) == 4 and sample.isdigit()) or self._is_valid_date(sample):
                return XSD.date
            
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
        if all(self._is_valid_date(v.strip()) for v in values if v.strip()):
            return XSD.date
            
        return XSD.string
    
    @staticmethod
    def _is_valid_date(value: str) -> bool:
        """Check if value is in YYYY-MM-DD format."""
        parts = value.split('-')
        return (len(parts) == 3 and 
                len(parts[0]) == 4 and 
                parts[0].isdigit() and
                parts[1].isdigit() and 
                parts[2].isdigit())
    
    def _add_numeric_constraints(self, prop_uri: URIRef, values: List[str], datatype: URIRef):
        """Add min/max constraints for numeric properties."""
        numeric_values = []
        for v in values:
            if v.strip():
                try:
                    if datatype == XSD.integer:
                        numeric_values.append(int(v))
                    else:
                        numeric_values.append(float(v))
                except ValueError:
                    continue
        
        if numeric_values:
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            
            self.g.add((prop_uri, SH.minInclusive, Literal(min_val, datatype=datatype)))
            self.g.add((prop_uri, SH.maxInclusive, Literal(max_val, datatype=datatype)))
            
            # # For integers, add exclusive constraints that are 1 unit beyond
            # if datatype == XSD.integer:
            #     self.g.add((prop_uri, SH.minExclusive, Literal(min_val - 1, datatype=datatype)))
            #     self.g.add((prop_uri, SH.maxExclusive, Literal(max_val + 1, datatype=datatype)))
    
    def _add_property_shape(self, node_shape: URIRef, property_name: str, 
                         property_type: URIRef, values: List[str]) -> None:
        """Add property shape with enhanced constraints."""
        safe_name = property_name.replace(' ', '_').replace('.', '_')
        prop_uri = URIRef(f"{self.base_uri}{safe_name}")
        
        self.g.add((prop_uri, RDF.type, SH.PropertyShape))
        self.g.add((prop_uri, SH.path, prop_uri))
        self.g.add((prop_uri, SH.datatype, property_type))
        
        # Add language tag if specified
        if self.default_lang:
            self.g.add((prop_uri, SH.name, Literal(property_name, lang=self.default_lang)))
        else:
            self.g.add((prop_uri, SH.name, Literal(property_name)))
        
        # Add numeric constraints if applicable
        if property_type in (XSD.integer, XSD.decimal):
            self._add_numeric_constraints(prop_uri, values, property_type)
        
        self.g.add((node_shape, SH.property, prop_uri))
    
    def transform_csv_to_shacl(self, csv_file: str, 
                            node_shape_name: Optional[str] = None, shape_identifier: Optional[str] = None) -> bool:
        """Transform CSV to SHACL with enhanced type detection."""
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
                
                if not rows:
                    print("CSV file is empty")
                    return False
                
                shape_name = node_shape_name or Path(csv_file).stem
                shape_uri = URIRef(f"{self.base_uri}{shape_identifier}")
                
                self.g.add((shape_uri, RDF.type, SH.NodeShape))
                self.g.add((shape_uri, SH.closed, Literal(True)))
                
                if self.default_lang:
                    self.g.add((shape_uri, SH.name, Literal(shape_name, lang=self.default_lang)))
                else:
                    self.g.add((shape_uri, SH.name, Literal(shape_name)))
                
                for column in reader.fieldnames:
                    clean_col = column.strip('\ufeff')
                    values = [row[clean_col] for row in rows if clean_col in row and row[clean_col]]
                    prop_type = self._guess_property_type(values, clean_col)
                    self._add_property_shape(shape_uri, clean_col, prop_type, values)
                
                return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def save_shacl(self, output_file: str) -> None:
        """Save the SHACL graph to Turtle format."""
        self.g.serialize(destination=output_file, format='turtle')
        print(f"SHACL shape saved to {output_file}")

if __name__ == "__main__":
    base_uri = "http://i14y.admin.ch/ns#"
    default_lang = "de" #change with your default language
    transformer = CSVToSHACL(base_uri)
    
    input_csv = "example/file.csv"
    output_ttl = "example/file.ttl"

    node_shape_name = " " # Optional - will use filename if None else you can state the file name "file_name"
    
    shape_identifer = " " # identifier to use in the uri -> base_uri/{shape_identifier}

    if transformer.transform_csv_to_shacl(input_csv, node_shape_name, shape_identifer):
        transformer.save_shacl(output_ttl)
    else:
        print("Failed to transform CSV to SHACL")
