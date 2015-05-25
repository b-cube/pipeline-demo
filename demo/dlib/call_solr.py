import requests
import json
import hashlib
import os


def pull_from_solr(output_directory):
    solr_url = 'http://54.191.81.42:8888/solr/collection1/select?q=*%3A*&wt=json&indent=true'

    # TODO: ask about auth for this
    req = requests.get(solr_url)

    if req.status_code != 200:
        raise

    new_data = req.json()

    for doc in new_data['response']['docs']:
        doc_url = doc['url']
        doc_sha = hashlib.sha224(doc_url).hexdigest()
        doc.update({"sha": doc_sha})

        with open(os.path.join(output_directory, '%s.json' % doc_sha), 'w') as f:
            f.write(json.dumps(doc, indent=4))
