import json
import requests
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, QB, OWL
import urllib3
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DSD2SHACLTransformer:
    """Class to transform Data Structure Definitions (DSD) to SHACL shapes."""
    
    def __init__(self, dataset_identifier: str):
        """Initialize the transformer with namespaces and RDF graph."""
        self.dataset_identifier = dataset_identifier
        self.g = Graph()
        self._initialize_namespaces()
        
    def _initialize_namespaces(self) -> None:
        """Set up all required namespaces and bind them to the graph."""
    
        i14y_base_path = f"https://www.i14y.admin.ch/resources/datasets/{self.dataset_identifier}/structure/"
    
        
        self.sh = Namespace("http://www.w3.org/ns/shacl#")
        self.i14y = Namespace(i14y_base_path)
        self.QB = Namespace("http://purl.org/linked-data/cube#")
        self.DCTERMS = Namespace("http://purl.org/dc/terms/")
        self.schema = Namespace("https://schema.org/")
        self.pav = Namespace("http://purl.org/pav/")
        self.rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        self.OWL = Namespace("http://www.w3.org/2002/07/owl#")

        self.g.bind("sh", self.sh)
        self.g.bind("i14y", self.i14y)
        self.g.bind("QB", self.QB)
        self.g.bind("dcterms", self.DCTERMS)
        self.g.bind("schema", self.schema)
        self.g.bind("pav", self.pav)
        self.g.bind("rdfs", self.rdfs)
        self.g.bind("owl", self.OWL)
    
    
    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Clean HTML text by removing tags and extra whitespace."""
        if not text:
            return ""
            
        soup = BeautifulSoup(text, "html.parser")
        cleaned_text = soup.get_text(separator=" ") 
        return " ".join(cleaned_text.split())
    
    @staticmethod
    def _api_get_request(url: str, token) -> Optional[Dict[str, Any]]:
        """Make a GET request to the API and return JSON response."""
        headers = {
                'Content-Type': 'application/json',  
                'Authorization': token 
            }
        response = requests.get(url, verify=False, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content)
        return None
    

    def get_dsd(self, id_dsd: str, token) -> Optional[Dict[str, Any]]:
        """gets the DSD metadata"""
        url = f"https://input.i14y.admin.ch/api/DataStructureDefinitionInput/{id_dsd}"
        return self._api_get_request(url, token)
    

    def get_data_elements(self, id_dsd: str, token) -> Optional[Dict[str, Any]]:
        """gets the data elements in the specific dsd"""
        url = f"https://input.i14y.admin.ch/api/DataStructureDefinitionInput/{id_dsd}/dataElements?page=1&pageSize=100"
        return self._api_get_request(url, token)
    

    def get_data_element_details(self, id_dataelement: str, token) -> Optional[Dict[str, Any]]:
        """gets details for a specific data element. """
        url = f"https://input.i14y.admin.ch/api/DataElementInput/{id_dataelement}"
        return self._api_get_request(url, token)
    

    def _add_dsd_metadata(self, dsd_node: URIRef, dsd_data: Dict[str, Any]) -> None:
        """Add metadata properties for the DSD node."""
        valid_from = dsd_data.get('validFrom', 'N/A')
        valid_until = dsd_data.get('validTo', 'N/A')
        version = dsd_data.get('version', 'N/A')
        name_dsd = dsd_data.get('name', {})
        #observation_units = dsd_data.get('observationUnits', [])
        
        self.g.add((dsd_node, RDF.type, QB.DataStructureDefinition))
        self.g.add((dsd_node, RDF.type, self.sh.NodeShape))
        self.g.add((dsd_node, RDF.type, self.rdfs.Class))
        self.g.add((dsd_node, self.schema.validFrom, Literal(valid_from, datatype=XSD.date)))
        if valid_until is not None: 
            self.g.add((dsd_node, self.schema.validUntil, Literal(valid_until, datatype=XSD.date)))
        self.g.add((dsd_node, self.schema.version, Literal(version)))
        self.g.add((dsd_node, self.pav.version, Literal(version)))
        #self.g.add((dsd_node, QB.observationGroup, ))
        
        for lang, value in name_dsd.items():
            if value:
                self.g.add((dsd_node, self.sh.name, Literal(value, lang=lang)))
                self.g.add((dsd_node, self.rdfs.label, Literal(value, lang=lang)))
    

    def _process_data_element(self, dsd_node: URIRef, entry: Dict[str, Any], token) -> None:
        """Process and add a data element to the RDF graph."""
        identifier = entry.get('identifier', 'N/A')
        id_dataelement = entry.get('id')
        
        data_element_details = self.get_data_element_details(id_dataelement, token)
        if not data_element_details:
            return
            
        self._add_data_element_properties(identifier, entry, data_element_details, dsd_node)
        self.g.add((dsd_node, self.sh.property, URIRef(dsd_node + "/" + identifier)))
    

    def _add_data_element_properties(self, identifier: str, entry: Dict[str, Any], 
                                   details: Dict[str, Any], dsd_node) -> None:
        """Add properties for a data element to the RDF graph."""
        property_node = URIRef(dsd_node + "/" + identifier)
        concept_id = details.get('conceptId', 'N/A')
        
        # Add basic properties
        self.g.add((property_node, RDF.type, self.sh.PropertyShape))
        self.g.add((property_node, RDF.type, self.OWL.DatatypeProperty))
        self.g.add((property_node, self.sh.order, Literal(entry.get('position', 'N/A'))))
       # self.g.add((property_node, self.DCTERMS.identifier, Literal(identifier)))
        self.g.add((property_node, self.sh.path, property_node))
        
        # Add multilingual properties
        self._add_multilingual_properties(property_node, entry)
        
        # Add role-specific properties
        self._add_role_properties(property_node, entry.get('role', 'N/A'))
        
        # Add type-specific properties
        self._add_type_properties(property_node, entry.get('type', 'N/A'), concept_id)
        
        # # Add concept reference
        # self.g.add((property_node, self.QB.concept, 
        #            URIRef(f"https://www.i14y.admin.ch/catalog/concepts/{concept_id}/description")))
        self.g.add((property_node, self.DCTERMS.conformsTo, 
                   URIRef(f"https://www.i14y.admin.ch/catalog/concepts/{concept_id}/description")))
    

    def _add_multilingual_properties(self, node: URIRef, entry: Dict[str, Any]) -> None:
        """Add multilingual name and description properties."""
        for lang, value in entry.get('name', {}).items():
            if value:
                cleaned_value = self._clean_text(value) #remove htlm tags 
                self.g.add((node, self.sh.name, Literal(cleaned_value, lang=lang)))
                
        for lang, value in entry.get('description', {}).items():
            if value:
                cleaned_value = self._clean_text(value) #remove html tags
                self.g.add((node, self.DCTERMS.description, Literal(cleaned_value, lang=lang)))
    

    def _add_role_properties(self, node: URIRef, role: str) -> None:
        """Add role-specific properties to a node."""
        if role == "Dimension":
            self.g.add((node, RDF.type, self.QB.DimensionProperty))
        elif role == "Measure":
            self.g.add((node, RDF.type, self.QB.MeasureProperty))
        elif role == "Attribute":
            self.g.add((node, RDF.type, self.QB.AttributeProperty))
    

    def _add_type_properties(self, node: URIRef, type_: str, concept_id: str) -> None:
        """Add type-specific properties to a node."""
        if type_ == "String":
            self.g.add((node, self.sh.datatype, XSD.string))
        elif type_ == "Numeric":
            self.g.add((node, self.sh.datatype, XSD.decimal))
        elif type_ == "Date":
            self.g.add((node, self.sh.datatype, XSD.date))
        elif type_ == "CodeList":
            self.g.add((node, RDF.type, self.QB.CodedProperty))
            # self.g.add((node, self.QB.codeList, 
            #            URIRef(f"https://www.i14y.admin.ch/de/catalog/concepts/{concept_id}/description")))
    

    def transform_to_shacl(self, id_dsd: str, output_path: str, token) -> bool:
        """Transform a DSD to SHACL and save to file."""
        dsd_data = self.get_dsd(id_dsd, token)
        if not dsd_data:
            print("Failed to retrieve DSD")
            return False
            
        identifier_dsd = dsd_data.get('identifier', 'N/A')
        id_dsd = dsd_data.get("id",'N/A' )
        dsd_node = URIRef(f"{self.i14y}{identifier_dsd}")
   
        
        self._add_dsd_metadata(dsd_node, dsd_data)
        
        data_elements = self.get_data_elements(id_dsd, token)
        if not data_elements:
            print("Failed to retrieve data elements")
            return False
            
        for entry in data_elements:
            self._process_data_element(dsd_node, entry, token)
        
        output_file = f"{output_path}{identifier_dsd}.ttl"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(self.g.serialize(format="turtle"))

        output_file = f"{output_path}{identifier_dsd}_jsonld.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(self.g.serialize(format="turtle"))
            
        print(f"\nDSD correctly transformed to SHACL \nIdentifier: {identifier_dsd} \nID: {id_dsd}  ")
        return True


if __name__ == "__main__":

    dsd_id = ""
    output_directory = "dsd_importer/example/"
    token = ""
    dataset_identifier = ""
    DSD_transformer = DSD2SHACLTransformer(dataset_identifier)
    DSD_transformer.transform_to_shacl(dsd_id, output_directory, token)

