from opensearch_preprocessors import OpenSearchReader
from xml_preprocessors import XmlReader


class Processor():
    '''
    just a little router for all of the preprocessors
    we have

    so we get processor.reader.parse_service()
    not great but let's hide all of the options away
    and not give the processors more than they need
    '''
    def __init__(self, identification, response, source_url):
        self.identity = identification
        self.source_url = source_url
        self._instantiate(response, source_url)

    def _instantiate(self, response, url):
        '''
        set up the router
        '''
        protocol = self.identity['protocol']

        if not protocol:
            # we will try a generic xml parser
            self.reader = XmlReader(response, url)

        if protocol == 'OpenSearch':
            self.reader = OpenSearchReader(response, url)

        return None
