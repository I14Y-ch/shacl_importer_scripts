import csv
from pathlib import Path
from typing import Optional, List
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD, SH

class CSVToSHACL:
    """Enhanced CSV to SHACL transformer with better year detection and numeric constraints."""
    
    YEAR_KEYWORDS = {
        'en': ['year', 'yr'],
        'de': ['jahr', 'jahrgang'],
        'fr': ['année', 'an'],
        'it': ['anno', 'annata']
    }
    
    def __init__(self, base_uri, default_lang: str = None):
        self.g = Graph()
        self.base_uri = base_uri.rstrip('/') + '/'
        self.default_lang = default_lang
        self.sh = SH
        self.g.bind("sh", SH)
        self.ex = Namespace(self.base_uri)
        self.g.bind("i14y", self.ex)

    def _is_year_column(self, column_name: str) -> bool:
        lower_name = column_name.lower()
        for keywords in self.YEAR_KEYWORDS.values():
            if any(keyword in lower_name for keyword in keywords):
                return True
        return False
    
    def _guess_property_type(self, values: List[str], column_name: str) -> URIRef:
        if not values:
            return XSD.string
            
        sample = values[0].strip() if values[0] else ""

        if self._is_year_column(column_name):
            if (len(sample) == 4 and sample.isdigit()) or self._is_valid_date(sample):
                return XSD.date
            
        if all(v.strip().isdigit() for v in values if v.strip()):
            return XSD.integer
            
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
            
        bool_values = {'true', 'false', 't', 'f', 'yes', 'no', '1', '0'}
        if all(v.strip().lower() in bool_values for v in values if v.strip()):
            return XSD.boolean
            
        if all(self._is_valid_date(v.strip()) for v in values if v.strip()):
            return XSD.date
            
        return XSD.string
    
    @staticmethod
    def _is_valid_date(value: str) -> bool:
        parts = value.split('-')
        return (len(parts) == 3 and 
                len(parts[0]) == 4 and 
                parts[0].isdigit() and
                parts[1].isdigit() and 
                parts[2].isdigit())
    
    def _add_numeric_constraints(self, prop_uri: URIRef, values: List[str], datatype: URIRef):
        numeric_values = []
        for v in values:
            if v.strip():
                try:
                    num_val = float(v)
                    if datatype == XSD.integer and num_val.is_integer():
                        numeric_values.append(int(num_val))
                    else:
                        numeric_values.append(num_val)
                except ValueError:
                    continue
        
        if numeric_values:
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            
            self.g.add((prop_uri, SH.minInclusive, Literal(min_val, datatype=datatype)))
            self.g.add((prop_uri, SH.maxInclusive, Literal(max_val, datatype=datatype)))
    
    def _add_property_shape(self, node_shape: URIRef, property_name: str, 
                         property_type: URIRef, values: List[str]) -> None:
        safe_name = property_name.replace(' ', '_').replace('.', '_')
        prop_uri = URIRef(f"{node_shape}/{safe_name}")
        
        self.g.add((prop_uri, RDF.type, SH.PropertyShape))
        self.g.add((prop_uri, SH.path, prop_uri))
        self.g.add((prop_uri, SH.datatype, property_type))
        
        if self.default_lang:
            self.g.add((prop_uri, SH.name, Literal(property_name, lang=self.default_lang)))
        else:
            self.g.add((prop_uri, SH.name, Literal(property_name)))
        
        if property_type in (XSD.integer, XSD.decimal):
            self._add_numeric_constraints(prop_uri, values, property_type)
        
        self.g.add((node_shape, SH.property, prop_uri))
    
    def transform_csv_to_shacl(self, csv_file: str, 
                            node_shape_name: Optional[str] = None, 
                            shape_identifier: Optional[str] = None,
                            delimiter: Optional[str] = None) -> bool:
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
            
                first_line = f.readline()
                f.seek(0)
                
                # Use specified delimiter or auto-detect
                used_delimiter = delimiter if delimiter else (';' if ';' in first_line else ',')
                
                reader = csv.DictReader(f, delimiter=used_delimiter)
                rows = list(reader)
                
                if not rows:
                    print("CSV file is empty")
                    return False
                
                shape_name = node_shape_name or Path(csv_file).stem
                shape_uri = URIRef(f"{self.base_uri}{shape_identifier or shape_name}")
                
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
            print(f"Error processing CSV: {e}")
            return False
    
    def save_shacl(self, output_file: str) -> None:
        self.g.serialize(destination=output_file, format='turtle')
        print(f"SHACL shape saved to {output_file}")


if __name__ == "__main__":
    dataset_identifier = "dataset_identifier"
    base_uri = "https://www.i14y.admin.ch/resources/datasets/" + dataset_identifier + "/structure/"
    default_lang = "de" #change with your default language
    transformer = CSVToSHACL(base_uri)
    
    input_csv = "csv_importer/example/iris.csv"
    output_ttl = "csv_importer/example/iris.ttl"

    node_shape_name = " " # Optional - will use filename if None else you can state the file name "file_name"
    shape_identifer = " " # Optional - identifier to use in the uri -> base_uri/{shape_identifier} - will use the file name if None (but file name should not contain spaces)

    if transformer.transform_csv_to_shacl(input_csv, node_shape_name, shape_identifer):
        transformer.save_shacl(output_ttl)
    else:
        print("Failed to transform CSV to SHACL")
