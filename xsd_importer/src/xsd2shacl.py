from lxml import etree
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS
import os
import re

dataset_identifier = "dataset_identifier" # state here the dataset identifier, needed to create the URI

i14y_base_path = "https://www.i14y.admin.ch/resources/datasets/" + dataset_identifier + "/structure/"
    


# Define namespaces
SH = Namespace("http://www.w3.org/ns/shacl#")
I14Y = Namespace(i14y_base_path)
DCT = Namespace("http://purl.org/dc/terms/")

def parse_xsd(xsd_file):
    """Parse the XSD file and return the root element."""
    with open(xsd_file, 'rb') as f:
        tree = etree.parse(f)
        root = tree.getroot()
        return root

def resolve_imports(xsd_root, base_path):
    """Resolve and parse imported XSD files."""
    imports = xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}import')
    for imp in imports:
        schema_location = imp.get('schemaLocation')
        if schema_location:
            import_path = os.path.join(base_path, schema_location)
            if os.path.exists(import_path):
                imported_root = parse_xsd(import_path)

def handle_enumeration(enumerations, subject, graph):
    """
    Handle XSD enumeration with sh:in.
    
    Args:
        enumerations: List of enumeration values
        subject: The RDF subject to add constraints to
        graph: The RDF graph
    """
    if not enumerations:
        return
    
    # Create a list node for the enumeration values
    enum_list = BNode()
    current = enum_list
    
    for i, enum_value in enumerate(enumerations):
        graph.add((current, RDF.first, Literal(enum_value)))
        if i < len(enumerations) - 1:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
        else:
            graph.add((current, RDF.rest, RDF.nil))
    
    graph.add((subject, SH["in"], enum_list))

def handle_union(union, xsd_root, subject, graph):
    """
    Handle XSD union with sh:or.
    
    Args:
        union: The XSD union element
        xsd_root: The root of the XSD document
        subject: The RDF subject to add constraints to
        graph: The RDF graph
    """
    if union is None:
        return
    
    member_types = union.findall('{http://www.w3.org/2001/XMLSchema}simpleType')
    if not member_types:
        return
    
    # Create an or list
    or_list = BNode()
    current = or_list
    
    for i, member_type in enumerate(member_types):
        restriction = member_type.find('{http://www.w3.org/2001/XMLSchema}restriction')
        if restriction:
            base = restriction.get('base')
            if base and ('xs:' in base or 'xsd:' in base):
                base_type = base.split(':')[-1]
                # Create a node for each member type
                member_node = BNode()
                graph.add((member_node, SH.datatype, XSD[base_type]))
                
                # Add facets if any
                for facet in restriction:
                    facet_name = facet.tag.split('}')[-1]
                    facet_value = facet.get('value')
                    if facet_value:
                        translate_restriction(facet_name, facet_value, base_type, member_node, graph)
                
                # Add to or list
                graph.add((current, RDF.first, member_node))
                if i < len(member_types) - 1:
                    next_node = BNode()
                    graph.add((current, RDF.rest, next_node))
                    current = next_node
                else:
                    graph.add((current, RDF.rest, RDF.nil))
    
    if or_list:
        graph.add((subject, SH.or_, or_list))

def handle_extension(extension, xsd_root, subject, graph):
    """
    Handle XSD extension with sh:and.
    
    Args:
        extension: The XSD extension element
        xsd_root: The root of the XSD document
        subject: The RDF subject to add constraints to
        graph: The RDF graph
    """
    if extension is None:
        return
    
    base = extension.get('base')
    if not base:
        return
    
    # Create an and list
    and_list = BNode()
    current = and_list
    
    # Add base type constraint
    if 'xs:' in base or 'xsd:' in base:
        base_type = base.split(':')[-1]
        base_node = BNode()
        graph.add((base_node, SH.datatype, XSD[base_type]))
        graph.add((current, RDF.first, base_node))
        
        # Add extension constraints
        extension_node = BNode()
        for elem in extension:
            if elem.tag.endswith('attribute'):
                handle_attribute(elem, xsd_root, graph, extension_node)
            elif elem.tag.endswith('sequence') or elem.tag.endswith('choice') or elem.tag.endswith('all'):
                # Handle content model extensions
                pass
        
        if len(list(extension_node.predicates())) > 0:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
            graph.add((current, RDF.first, extension_node))
        
        graph.add((current, RDF.rest, RDF.nil))
        graph.add((subject, SH.and_, and_list))
    else:
        # Handle custom base types
        type_name = base.split(':')[-1]
        base_node = BNode()
        graph.add((base_node, SH['class'], I14Y[type_name]))
        graph.add((current, RDF.first, base_node))
        
        # Add extension constraints
        extension_node = BNode()
        for elem in extension:
            if elem.tag.endswith('attribute'):
                handle_attribute(elem, xsd_root, graph, extension_node)
            elif elem.tag.endswith('sequence') or elem.tag.endswith('choice') or elem.tag.endswith('all'):
                # Handle content model extensions
                pass
        
        if len(list(extension_node.predicates())) > 0:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
            graph.add((current, RDF.first, extension_node))
        
        graph.add((current, RDF.rest, RDF.nil))
        graph.add((subject, SH.and_, and_list))

def _process_simple_type(simple_type, xsd_root):
    """Process a simpleType definition and return type details."""
    restriction = simple_type.find('{http://www.w3.org/2001/XMLSchema}restriction')
    union = simple_type.find('{http://www.w3.org/2001/XMLSchema}union')
    
    if restriction is not None:
        base = restriction.get('base')
        facets = {}
        enumerations = []
        
        for facet in restriction:
            facet_name = facet.tag.split('}')[-1]
            facet_value = facet.get('value')
            if facet_value:
                if facet_name == 'enumeration':
                    enumerations.append(facet_value)
                else:
                    facets[facet_name] = facet_value
        
        if base and ('xs:' in base or 'xsd:' in base):
            return ('simple', base.split(':')[-1], {
                'facets': facets,
                'enumerations': enumerations
            })
        elif base:
            # Handle custom base types
            base_type_name = base.split(':')[-1]
            base_simple_type = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}simpleType[@name="{base_type_name}"]')
            if base_simple_type:
                base_kind, base_type, base_facets = _process_simple_type(base_simple_type, xsd_root)
                # Merge facets
                facets.update(base_facets.get('facets', {}))
                enumerations.extend(base_facets.get('enumerations', []))
                return ('simple', base_type, {
                    'facets': facets,
                    'enumerations': enumerations
                })
    
    elif union is not None:
        member_types = []
        for member in union.findall('{http://www.w3.org/2001/XMLSchema}simpleType'):
            restriction = member.find('{http://www.w3.org/2001/XMLSchema}restriction')
            if restriction:
                base = restriction.get('base')
                if base and ('xs:' in base or 'xsd:' in base):
                    member_types.append(base.split(':')[-1])
        return ('union', member_types, {})
    
    return ('simple', 'string', {})

def translate_restriction(facet_name, facet_value, base_type=None, subject=None, graph=None):
    """
    Translates XSD restrictions to SHACL constraints.
    """
    # Numeric constraints
    numeric_facets = {
        'minInclusive': SH.minInclusive,
        'maxInclusive': SH.maxInclusive,
        'minExclusive': SH.minExclusive,
        'maxExclusive': SH.maxExclusive,
        'totalDigits': SH.totalDigits,
        'fractionDigits': SH.fractionDigits
    }
    
    # String constraints
    string_facets = {
        'minLength': SH.minLength,
        'maxLength': SH.maxLength,
        'length': (SH.minLength, SH.maxLength),
        'pattern': SH.pattern,
        'enumeration': SH["in"]
    }
    
    # Convert value to appropriate type
    if facet_name in ['minLength', 'maxLength', 'length', 'totalDigits', 'fractionDigits']:
        value = Literal(int(facet_value), datatype=XSD.integer)
    elif facet_name in numeric_facets and base_type:
        value = Literal(facet_value, datatype=XSD[base_type])
    elif facet_name == 'pattern':
        value = Literal(facet_value.replace('\\', '\\\\'))
    elif facet_name == 'enumeration':
        if graph and subject:
            # Create a blank node for the enumeration list
            enum_list = URIRef(f"http://example.org/enum/{subject.split('/')[-1]}")
            graph.add((enum_list, RDF.first, Literal(facet_value)))
            graph.add((enum_list, RDF.rest, RDF.nil))
            graph.add((subject, SH['in'], enum_list))
            return None
        return (SH['in'], Literal(facet_value))
    else:
        value = Literal(facet_value)
    
    # Determine the predicate(s)
    if facet_name in numeric_facets:
        predicate = numeric_facets[facet_name]
    elif facet_name in string_facets:
        if facet_name == 'length':
            if graph and subject:
                graph.add((subject, SH.minLength, value))
                graph.add((subject, SH.maxLength, value))
                return None
            return (SH.minLength, value), (SH.maxLength, value)
        predicate = string_facets[facet_name]
    else:
        return None
    
    if graph and subject:
        graph.add((subject, predicate, value))
        return None
    return (predicate, value)


def handle_sequence(sequence, xsd_root, graph, parent_shape, parent_type_name):
    """
    Handle XSD sequence with order constraints.
    Adds properties with sh:order to maintain sequence.
    """
    if sequence is None:
        return
    
    order = 0
    for element in sequence.findall('{http://www.w3.org/2001/XMLSchema}element'):
        element_name = element.get('name')
        if element_name:
            # Create unique property shape URI based on parent type and element name
            prop_shape = I14Y[f"{parent_type_name}/{element_name}"]   # THIS IS THE SOLUTION FOR THE BUG, BUT IT COULD BE _ OR /
            graph.add((prop_shape, RDF.type, SH.PropertyShape))
            graph.add((prop_shape, SH.path, I14Y[f"{parent_type_name}/{element_name}"] ))
            graph.add((prop_shape, SH.name, Literal(element_name, lang='en')))
            graph.add((prop_shape, SH.order, Literal(order, datatype=XSD.integer)))
            
            # Process element details
            process_element_details(element, xsd_root, graph, prop_shape)
            
            graph.add((parent_shape, SH.property, prop_shape))
            order += 1

def handle_choice(choice,  xsd_root, graph, parent_shape, parent_type_name):
    """
    Handle XSD choice with sh:xone (exclusive or).
    """
    if choice is None:
        return
    
    # Create a blank node for the xone list
    xone_list = URIRef(f"http://example.org/xone/{parent_shape.split('/')[-1]}")
    last_node = None
    
    elements = choice.findall('{http://www.w3.org/2001/XMLSchema}element')
    for i, element in enumerate(elements):
        element_name = element.get('name')
        if element_name is not None:
            current_node = URIRef(f"{xone_list}_{i}")
            graph.add((current_node, RDF.first, I14Y[f"{parent_type_name}/{element_name}"] ))
            if last_node:
                graph.add((last_node, RDF.rest, current_node))
            else:
                graph.add((xone_list, RDF.first, current_node))
            last_node = current_node
    
    if last_node:
        graph.add((last_node, RDF.rest, RDF.nil))
        graph.add((parent_shape, SH.xone, xone_list))

def handle_all(all_elem, xsd_root, graph, parent_shape, parent_type_name):
    """
    Handle XSD all compositor (all properties required, no order).
    """
    if all_elem is None:
        return
    
    for element in all_elem.findall('{http://www.w3.org/2001/XMLSchema}element'):
        element_name = element.get('name')
        if element_name:
            prop_shape = I14Y[f"{parent_type_name}/{element_name}"] 
            # All elements are required (minCount=1)
            graph.add((prop_shape, SH.minCount, Literal(1, datatype=XSD.integer)))
            graph.add((parent_shape, SH.property, prop_shape))


def handle_extension(extension, xsd_root):
    """
    Handles XSD extension elements, returning base type and any additional facets.
    
    Args:
        extension: The XSD extension element
        xsd_root: The root of the XSD document
        
    Returns:
        A tuple (base_type, facets) where:
        - base_type: The base type being extended
        - facets: Dictionary of additional constraints
    """
    base = extension.get('base')
    facets = {}
    
    if not base:
        return (None, facets)
    
    # Check if base is a built-in type
    if 'xs:' in base or 'xsd:' in base:
        return (base.split(':')[-1], facets)
    
    # Handle custom base types
    base_type_name = base.split(':')[-1]
    
    # Check if base is a simpleType
    simple_type = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}simpleType[@name="{base_type_name}"]')
    if simple_type:
        restriction = simple_type.find('{http://www.w3.org/2001/XMLSchema}restriction')
        if restriction:
            base_type = restriction.get('base')
            if base_type and ('xs:' in base_type or 'xsd:' in base_type):
                return (base_type.split(':')[-1], facets)
    
    return (None, facets)


def translate_annotation(xsd_element, subject, graph):
    """
    Converts XSD annotations (documentation/appinfo) to SHACL descriptions.
    
    Args:
        xsd_element: The XSD element containing annotations
        subject: The RDF subject to add annotations to
        graph: The RDF graph to add triples to
    """
    annotations = xsd_element.find('.//{http://www.w3.org/2001/XMLSchema}annotation')
    if annotations is not None:
        # Handle documentation elements (descriptions)
        for doc in annotations.findall('.//{http://www.w3.org/2001/XMLSchema}documentation'):
            lang = doc.get('{http://www.w3.org/XML/1998/namespace}lang', 'en')
            if doc.text and doc.text.strip():
                graph.add((subject, DCT.description, Literal(doc.text.strip(), lang=lang)))
        
        # Handle appinfo elements (could be used for other metadata)
        for appinfo in annotations.findall('.//{http://www.w3.org/2001/XMLSchema}appinfo'):
            # You could add custom processing for appinfo here
            pass


def handle_attribute(attribute, xsd_root, graph, parent_shape=None, parent_type_name=None):
    """
    Handles XSD attribute definitions by creating PropertyShapes.
    
    Args:
        attribute: The XSD attribute element
        xsd_root: The root of the XSD document
        graph: The RDF graph
        parent_shape: Optional parent NodeShape for the attribute
    """
    attr_name = attribute.get('name') or attribute.get('ref')
    if not attr_name:
        return None
    
    # Handle attribute references (ref="...")
    if attribute.get('ref'):
        attr_name = attribute.get('ref').split(':')[-1]
        # Look up the attribute definition
        attribute = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}attribute[@name="{attr_name}"]')
        if not attribute:
            return None
    
    # Create a PropertyShape for the attribute
    attr_shape = I14Y[f"{parent_type_name}/{attr_name}"] 
    graph.add((attr_shape, RDF.type, SH.PropertyShape))
    graph.add((attr_shape, SH.path, I14Y[f"{parent_type_name}/{attr_name}"] ))
    graph.add((attr_shape, SH.name, Literal(attr_name, lang='en')))
    
    # Handle attribute type
    attr_type = attribute.get('type')
    if attr_type:
        if 'xs:' in attr_type or 'xsd:' in attr_type:
            # Built-in type
            datatype = attr_type.split(':')[-1]
            graph.add((attr_shape, SH.datatype, XSD[datatype]))
        else:
            # Custom type
            type_name = attr_type.split(':')[-1]
            simple_type = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}simpleType[@name="{type_name}"]')
            if simple_type:
                type_kind, base_type, facets = _process_simple_type(simple_type, xsd_root)
                if base_type:
                    graph.add((attr_shape, SH.datatype, XSD[base_type]))
                for facet_name, facet_value in facets.items():
                    translate_restriction(facet_name, facet_value, base_type, attr_shape, graph)
    
    # Handle inline simpleType
    simple_type = attribute.find('{http://www.w3.org/2001/XMLSchema}simpleType')
    if simple_type is not None:
        type_kind, base_type, facets = _process_simple_type(simple_type, xsd_root)
        if base_type:
            graph.add((attr_shape, SH.datatype, XSD[base_type]))
        for facet_name, facet_value in facets.items():
            translate_restriction(facet_name, facet_value, base_type, attr_shape, graph)
    
    # Handle use (required/optional)
    use = attribute.get('use', 'optional')
    if use == 'required':
        graph.add((attr_shape, SH.minCount, Literal(1, datatype=XSD.integer)))
    else:
        graph.add((attr_shape, SH.minCount, Literal(0, datatype=XSD.integer)))
    
    # Handle default and fixed values
    if attribute.get('default'):
        graph.add((attr_shape, SH.defaultValue, Literal(attribute.get('default'))))
    if attribute.get('fixed'):
        graph.add((attr_shape, SH.hasValue, Literal(attribute.get('fixed'))))
    
    # Handle annotations
    translate_annotation(attribute, attr_shape, graph)
    
    # If we have a parent shape, link the attribute to it
    if parent_shape:
        graph.add((parent_shape, SH.property, attr_shape))
    
    return attr_shape



def _process_complex_type(complex_type, xsd_root):
    """Process a complexType definition and return type details."""
    if complex_type.get('mixed') == 'true':
        return ('complex_mixed', None, {})
    
    simple_content = complex_type.find('{http://www.w3.org/2001/XMLSchema}simpleContent')
    complex_content = complex_type.find('{http://www.w3.org/2001/XMLSchema}complexContent')
    
    if simple_content is not None:
        extension = simple_content.find('{http://www.w3.org/2001/XMLSchema}extension')
        restriction = simple_content.find('{http://www.w3.org/2001/XMLSchema}restriction')
        
        if extension is not None:
            base_type, facets = handle_extension(extension, xsd_root)
            attrs = {}
            for attr in extension.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
                attrs[attr.get('name')] = attr
            return ('complex_simple_content', base_type, {'attributes': attrs})
        elif restriction is not None:
            base = restriction.get('base')
            if base and ('xs:' in base or 'xsd:' in base):
                # Process restriction facets
                facets = {}
                for facet in restriction.findall('{http://www.w3.org/2001/XMLSchema}*'):
                    facet_name = facet.tag.split('}')[-1]
                    facet_value = facet.get('value')
                    if facet_value:
                        facets[facet_name] = facet_value
                return ('complex_simple_content', base.split(':')[-1], {'facets': facets})
    
    elif complex_content is not None:
        extension = complex_content.find('{http://www.w3.org/2001/XMLSchema}extension')
        restriction = complex_content.find('{http://www.w3.org/2001/XMLSchema}restriction')
        
        if extension is not None:
            base = extension.get('base')
            if base:
                attrs = {}
                for attr in extension.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
                    attrs[attr.get('name')] = attr
                return ('complex', base.split(':')[-1], {'attributes': attrs})
        elif restriction is not None:
            base = restriction.get('base')
            if base:
                return ('complex', base.split(':')[-1], {})
    
    # Check for compositors (sequence, choice, all)
    compositors = {
        'sequence': None,
        'choice': None,
        'all': None
    }
    
    for compositor in compositors:
        elem = complex_type.find(f'{{http://www.w3.org/2001/XMLSchema}}{compositor}')
        if elem is not None:
            compositors[compositor] = elem
            break
    
    # Collect attributes
    attrs = {}
    for attr in complex_type.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
        attrs[attr.get('name')] = attr
    for attr_group in complex_type.findall('{http://www.w3.org/2001/XMLSchema}attributeGroup'):
        attr_group_ref = attr_group.get('ref')
        if attr_group_ref:
            group_name = attr_group_ref.split(':')[-1]
            attr_group_def = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}attributeGroup[@name="{group_name}"]')
            if attr_group_def:
                for attr in attr_group_def.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
                    attrs[attr.get('name')] = attr
    
    return ('complex', None, {
        'compositors': compositors,
        'attributes': attrs
    })

def process_element_details(element, xsd_root, graph, prop_shape):
    """
    Process element details and add to property shape.
    """
    translate_annotation(element, prop_shape, graph)

    type_kind, base_type, facets = get_element_type_details(xsd_root, element)
    
    if type_kind in ['builtin', 'simple']:
        if base_type:
            graph.add((prop_shape, SH.datatype, XSD[base_type]))
        
        if 'facets' in facets:
            for facet_name, facet_value in facets['facets'].items():
                translate_restriction(facet_name, facet_value, base_type, prop_shape, graph)
        
        if 'enumerations' in facets:
            handle_enumeration(facets['enumerations'], prop_shape, graph)
    
    elif type_kind == 'union':
        handle_union(element.find('{http://www.w3.org/2001/XMLSchema}union'), xsd_root, prop_shape, graph)
    
    elif type_kind in ['complex', 'complex_mixed', 'complex_simple_content']:
        type_name = element.get('type').split(':')[-1] if element.get('type') else None
        if type_name:
            graph.add((prop_shape, SH['class'], I14Y[type_name]))
    
    if type_kind in ['simple', 'complex', 'complex_mixed', 'complex_simple_content', 'union']:
        type_name = element.get('type').split(':')[-1] if element.get('type') else None
        if type_name:
            graph.add((prop_shape, DCT.conformsTo, I14Y[type_name]))

    # Handle minOccurs and maxOccurs
    min_occurs = element.get('minOccurs', '1')
    max_occurs = element.get('maxOccurs', '1')

    graph.add((prop_shape, SH.minCount, Literal(int(min_occurs), datatype=XSD.integer)))
    if max_occurs != "unbounded":
        graph.add((prop_shape, SH.maxCount, Literal(int(max_occurs), datatype=XSD.integer)))
    else:
        graph.add((prop_shape, SH.maxCount, SH.unbounded))

def get_element_type_details(xsd_root, element):
    """
    Determine the type of an XSD element and return details.
    """
    element_type = element.get('type')
    if not element_type:
        # Check for inline type definition
        simple_type = element.find('{http://www.w3.org/2001/XMLSchema}simpleType')
        complex_type = element.find('{http://www.w3.org/2001/XMLSchema}complexType')
        if simple_type is not None:
            return _process_simple_type(simple_type, xsd_root)
        elif complex_type is not None:
            return _process_complex_type(complex_type, xsd_root)
        else:
            return ('builtin', 'string', {})  # Default to string if no type info
    
    if 'xs:' in element_type or 'xsd:' in element_type:
        # Built-in simple type
        return ('builtin', element_type.split(':')[-1], {})
    
    # Custom type - could be simple or complex
    type_name = element_type.split(':')[-1]
    
    # Check for simpleType first
    simple_type = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}simpleType[@name="{type_name}"]')
    if simple_type is not None:
        return _process_simple_type(simple_type, xsd_root)
    
    # Check for complexType
    complex_type = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}complexType[@name="{type_name}"]')
    if complex_type is not None:
        return _process_complex_type(complex_type, xsd_root)
    
    # If we can't determine, assume builtin string
    return ('builtin', 'string', {})

def generate_shacl(xsd_root):
    """Generate SHACL shapes from the XSD schema."""
    g = Graph()
    g.bind("sh", SH)
    g.bind("i14y", I14Y)
    g.bind("dct", DCT)

    # First pass: collect all element definitions
    element_defs = {}
    for element in xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
        name = element.get('name')
        if name:
            element_defs[name] = element

    # Process complex types to create NodeShapes
    type_map = {}
    for complex_type in xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}complexType'):
        type_name = complex_type.get('name')
        if type_name:
            type_map[type_name] = complex_type
            node_shape = I14Y[type_name]
            g.add((node_shape, RDF.type, SH.NodeShape))
            g.add((node_shape, SH.name, Literal(type_name, lang='en')))

            type_kind, base_type, facets = _process_complex_type(complex_type, xsd_root)
            
            # Handle inheritance
            if base_type and type_kind == 'complex':
                g.add((node_shape, SH['class'], I14Y[base_type]))
            
            # Handle compositors
            if 'compositors' in facets:
                if facets['compositors']['sequence'] is not None:
                    handle_sequence(facets['compositors']['sequence'], xsd_root, g, node_shape, type_name)
                elif facets['compositors']['choice'] is not None:
                    handle_choice(facets['compositors']['choice'], xsd_root, g, node_shape, type_name)
                elif facets['compositors']['all'] is not None:
                    handle_all(facets['compositors']['all'], xsd_root, g, node_shape, type_name)
            
            # Handle attributes
            if 'attributes' in facets:
                for attr_name, attribute in facets['attributes'].items():
                    handle_attribute(attribute, xsd_root, g, node_shape)
            
            g.add((node_shape, SH.closed, Literal(True)))

    return g

def save_shacl(g, output_file):
    """Save the SHACL graph to an RDF file."""
    g.serialize(destination=output_file, format='turtle')

def xsd_to_shacl(xsd_file, output_file, base_path):
    """Convert an XSD schema to a SHACL RDF file."""
    xsd_root = parse_xsd(xsd_file)
    resolve_imports(xsd_root, base_path)
    shacl_graph = generate_shacl(xsd_root)
    save_shacl(shacl_graph, output_file)



# Example usage
xsd_to_shacl("xsd_importer/example/eCH-0108-7-0.xsd", 'xsd_importer/example/master_unit.ttl', 'xsd_importer/example')