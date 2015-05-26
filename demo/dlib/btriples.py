#!/usr/bin/env python

from rdflib import Graph, Literal, RDF, RDFS, Namespace, URIRef
from rdflib.namespace import DCTERMS
from rdflib.plugins.stores import sparqlstore
from bunch import bunchify
import hashlib
import json
from uuid import uuid4


class LocalStore():
    '''
    This class is a wrapper for the Graph class that
    handles ontology binding and triples serialization.
    '''

    def __init__(self):
        self.g = Graph()
        self.ns = {}

    def bind_namespaces(self, namespaces):
        for ns in namespaces:
            # ns is the prefix and the key
            self.g.bind(ns, Namespace(namespaces[ns]))
            self.ns[ns] = Namespace(namespaces[ns])

    def get_namespaces(self):
        ns = []
        for namespace in self.g.namespaces():
            ns.append(namespace)
        return ns

    def get_resource(self, urn):
        return self.g.resource(urn)

    def add_triple(self, s, v, p):
        self.g.add((s, v, p))

    def serialize(self, format):
        return self.g.serialize(format=format)


class RemoteStore():
    def __init__(self, endpoint):
        self._store = sparqlstore.SPARQLUpdateStore()
        self._store.open((endpoint, endpoint))
        self.g = Graph(self._store, URIRef('urn:x-arq:DefaultGraph'))

    def update(self, triples_as_nt):
        return self.g.update("INSERT DATA { %s }" % triples_as_nt)

    def delete(self, triples_as_nt):
        return self.g.update("DELETE DATA { %s }" % triples_as_nt)


class Triplelizer():
    '''
    This class takes the json output from semantics-preprocessing and generates
    triples
    '''
    def __init__(self):
        self.store = LocalStore()
        with open('configs/services.json', 'r') as fp:
            self.fingerprints = bunchify(json.loads(fp.read()))
        ontology_uris = {
            'wso': 'http://purl.org/nsidc/bcube/web-services#',
            'Profile': 'http://www.daml.org/services/owl-s/1.2/Profile.owl#',
            'Service': 'http://ww.daml.org/services/owl-s/1.2/Service.owl#',
            'ServiceParameter':
            'http://www.daml.org/services/owl-s/1.2/ServiceParameter.owl#',
            'media':
            'http://www.iana.org/assignments/media-types/media-types.xhtml#',
            'dc': str(DCTERMS)
        }
        self.store.bind_namespaces(ontology_uris)

    def _validate(self, value):
        '''
        Returns None if the value is empty string,
        'null' or is non existant.
        '''
        if value == "" or value == "null" or value is None:
            return None
        else:
            return value

    def _escape_rdflib(self, url):
        '''
        See http://github.com/RDFLib/rdflib/blob/
        e80c6186fee68219e19bc2adae2cd5edf20bfef9/rdflib/term.py
        Line 73
        '''
        return url.replace("{", "%7B").replace("}", "%7D")

    def _generate_sha_identifier(self, url):
        '''
        temporary document identifer as sha-1 of the source url
        (should be implemented in solr in the near future)
        '''
        return hashlib.sha224(url).hexdigest()

    def _generate_uri(self, object_type):
        '''
        generate a non-resolvable uri for any object as
            urn:{object_type}:{identifier}
        where object_type is the class name and identifier
        is a random hash (uuid4 for now)

        note: can't just generate a sha hash from the value
              given that the values can repeat
        '''
        return 'urn:{0}:{1}'.format(object_type, str(uuid4()))

    def identify(self, document):
        for attr in self.fingerprints:
            if attr.DocType == document.identity.protocol:
                return attr.object_type, attr.ontology_class
        return None

    def triplelize_parameters(self, parameters, endpoint, digest):
        '''
        Triplelize parameters, they belong to an endpoint
        and have a name, type and format.
        '''
        param_ns = self.store.ns['ServiceParameter']
        for param in parameters:
            parameter_urn = self._generate_uri('ServiceParameter')
            p = self.store.get_resource(parameter_urn)

            p.add(RDF.type, URIRef("ServiceParameter:ServiceParameter"))
            if self._validate(param.name) is not None:
                p.add(param_ns['serviceParameterName'],
                      Literal(param.name))
            if 'formats' in param and self._validate(param.formats) is not None:
                p.add(param_ns['serviceParameterFormat'],
                      Literal(param.formats))
            if 'type' in param and self._validate(param.type) is not None:
                p.add(param_ns['serviceParameterType'],
                      Literal(param.type))
            endpoint.add(param_ns['hasParameters'], p)
        return self.store

    def triplelize_endpoints(self, doc, service):
        '''
        '''
        wso = self.store.ns['wso']
        media = self.store.ns['media']

        for item in doc.service_description.service.endpoints:
            endpoint_uri = self._generate_uri('ServiceEndpoint')
            endpoint = self.store.get_resource(endpoint_uri)

            endpoint.add(wso["Protocol"], Literal(item.protocol))
            endpoint.add(wso["BaseURL"], URIRef(self._escape_rdflib(item.url)))
            if 'mimeType' in item and item.mimeType is not None:
                for mime_type in item.mimeType:
                    endpoint.add(media['type'], Literal(mime_type))

            if doc.identity.subtype == "service":
                endpoint.add(RDF.type, wso["ServiceEndpoint"])
                endpoint.add(wso["hasService"], service)
                if 'parameters' in item and item.parameters is not None:
                    self.triplelize_parameters(item.parameters,
                                               endpoint, doc.digest)
            else:
                endpoint.add(wso["childOf"], service)

            if 'name' in item:
                endpoint.add(RDFS.label, Literal(item.name))
        return self.store

    def triplelize(self, document):
        '''
        This method works fine with:
        pip install git+https://github.com/betolink/bunch.git
        Otherwise bunch rises an exception for not found keys
        '''
        # ns = 'http://purl.org/nsidc/bcube/web-services#'
        wso = self.store.ns['wso']
        if self.identify(document) is not None:
            document_urn = self._generate_uri('WebDocument')

            service_doc = document.get('service_description', {})
            service = service_doc.get('service', {})

            if not service_doc or not service:
                return None

            doc_base_url = document.url
            doc_version = document.identity.version
            doc_title = service.get('title', [])
            doc_abstract = service.get('abstract', [])
            doc_type, doc_ontology = self.identify(document)

            resource = self.store.get_resource(document_urn)

            resource.add(RDF.type, URIRef(doc_type))
            resource.add(RDF.type, wso[doc_ontology])
            resource.add(DCTERMS.hasVersion, Literal(doc_version))

            # run as multiple elements for now
            for title in doc_title:
                resource.add(DCTERMS.title, Literal(title))
            for abstract in doc_abstract:
                resource.add(DCTERMS.abstract, Literal(abstract))

            resource.add(wso.BaseURL,
                         Literal(self._escape_rdflib(doc_base_url)))
            # now the endpoints
            self.triplelize_endpoints(document, resource)
            return self.store, document_urn
        else:
            return None, None


def triplify(json_data):
    json_data = bunchify(json_data)
    triple = Triplelizer()
    return triple.triplelize(json_data)


def storify(endpoint, triples_as_nt=None, triples_path='', option='INSERT'):
    '''
    load an existing set of triples as TURTLE ONLY
    or just accept a set of triples already serialized as nt
    '''
    store = RemoteStore(endpoint)
    if triples_path:
        # load the triples from the path as nt
        g = Graph()
        g.parse(triples_path, format='turtle')
        triples_as_nt = g.serialize(format='nt')

    if triples_as_nt is None:
        raise Exception('No triples!')

    if option == 'INSERT':
        store.update(triples_as_nt)
    elif option == 'DELETE':
        store.delete(triples_as_nt)
