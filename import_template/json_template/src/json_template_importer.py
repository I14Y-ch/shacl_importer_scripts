import json
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS

def json_to_shacl(json_input, output_file):

    SH = Namespace("http://www.w3.org/ns/shacl#")
    DCTERMS = Namespace("http://purl.org/dc/terms/")
    BASE_URI = "https://www.i14y.admin.ch/resources/datasets/structure/"
    
    g = Graph()
    
    g.bind("sh", SH)
    g.bind("dcterms", DCTERMS)
    g.bind("xsd", XSD)
    g.bind("i14y", BASE_URI)
    
    try:
        data = json.loads(json_input)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return
    
    # First: Create all NodeShapes
    node_shapes = {}
    for cls in data.get("classes", []):
        class_uri = URIRef(f"{BASE_URI}{cls['identifier']}")
        node_shapes[cls['identifier']] = class_uri
        g.add((class_uri, RDF.type, SH.NodeShape))
        

        for lang, name in cls.get("names", {}).items():
            g.add((class_uri, SH.name, Literal(name, lang=lang)))
        

        if "descriptions" in cls:
            for lang, desc in cls["descriptions"].items():
                g.add((class_uri, DCTERMS.description, Literal(desc, lang=lang)))
        
        if "modified" in cls:
            g.add((class_uri, DCTERMS.modified, Literal(cls["modified"], datatype=XSD.dateTime)))
        
        if "created" in cls:
            g.add((class_uri, DCTERMS.created, Literal(cls["created"], datatype=XSD.dateTime)))
        
        if "identifier" in cls:
            g.add((class_uri, DCTERMS.identifier, Literal(cls["identifier"])))
        

        if cls.get("closed", False):
            g.add((class_uri, SH.closed, Literal(True)))
    
    # Second :  properties and relations
    for cls in data.get("classes", []):
        class_uri = node_shapes[cls['identifier']]
        

        for prop in cls.get("properties", []):
            prop_uri = URIRef(f"{BASE_URI}{cls['identifier']}/{prop['identifier']}")
            g.add((class_uri, SH.property, prop_uri))
            g.add((prop_uri, RDF.type, SH.PropertyShape))
            g.add((prop_uri, SH.path, prop_uri))
            

            for lang, name in prop.get("names", {}).items():
                g.add((prop_uri, SH.name, Literal(name, lang=lang)))

            datatype_map = {
                "string": XSD.string,
                "dateTime": XSD.dateTime,
                "integer": XSD.integer,
                "boolean": XSD.boolean
            }
            if "datatype" in prop:
                datatype = prop["datatype"]
                if datatype in datatype_map:
                    g.add((prop_uri, SH.datatype, datatype_map[datatype]))
                else:
                    print(f"Warning: Unknown datatype {datatype} for property {prop['identifier']}")
            

            constraints = prop.get("constraints", {})
            for constraint, value in constraints.items():
                if constraint in ["pattern"]: 
                    g.add((prop_uri, SH[constraint], Literal(value))) 
                if constraint in ["minCount", "maxCount", "minLength", "maxLength", "uniqueLang"]:
                    if constraint in ["minCount", "maxCount", "minLength", "maxLength"]:
                        value = Literal(value, datatype=XSD.integer)
                    g.add((prop_uri, SH[constraint], value))
            

            if "order" in prop:
                g.add((prop_uri, SH.order, Literal(prop["order"], datatype=XSD.integer)))
            
 
            if "conformsTo" in prop:
                g.add((prop_uri, DCTERMS.conformsTo, URIRef(prop["conformsTo"])))
        
        # Process relations (properties that reference other NodeShapes)
        for rel in cls.get("relations", []):
            rel_uri = URIRef(f"{BASE_URI}{cls['identifier']}/{rel['identifier']}")
            g.add((class_uri, SH.property, rel_uri))
            g.add((rel_uri, RDF.type, SH.PropertyShape))
            g.add((rel_uri, SH.path, rel_uri))
            

            for lang, name in rel.get("names", {}).items():
                g.add((rel_uri, SH.name, Literal(name, lang=lang)))
            

            if "class" in rel:
                target_class_uri = URIRef(f"{BASE_URI}{rel['class']}")
                g.add((rel_uri, SH["class"], target_class_uri))
            
       
            constraints = rel.get("constraints", {})
            for constraint, value in constraints.items():
                if constraint in ["pattern"]: 
                    g.add((rel_uri, SH[constraint], Literal(value))) 
                if constraint in ["minCount", "maxCount", "minLength", "maxLength", "uniqueLang"]:
                    if constraint in ["minCount", "maxCount", "minLength", "maxLength"]:
                        value = Literal(value, datatype=XSD.integer)
                    g.add((rel_uri, SH[constraint], value))
            

            if "order" in rel:
                g.add((rel_uri, SH.order, Literal(rel["order"], datatype=XSD.integer)))
            
       
            if "conformsTo" in rel:
                g.add((rel_uri, DCTERMS.conformsTo, URIRef(rel["conformsTo"])))
    

    g.serialize(destination=output_file, format="turtle", encoding="utf-8")
    print(f"SHACL file generated successfully at {output_file}")



if __name__ == "__main__":
  
    with open("json_template/template_json.json", "r", encoding="utf-8") as f:
        json_input = f.read()
    

    json_input = json_input.replace('}\n    {', '},\n    {')
    
    
    json_to_shacl(json_input, "output.ttl")
