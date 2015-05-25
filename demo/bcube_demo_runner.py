import luigi
from dlib.bcube_demo_pipeline import MainWorkflow
import requests
import json
import hashlib


def pull_from_solr():
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

        with open('bcube_demo/docs/%s.json' % doc_sha, 'w') as f:
            f.write(json.dumps(doc, indent=4))


if __name__ == '__main__':
    pull_from_solr()
    w = MainWorkflow(doc_dir='bcube_demo/docs', yaml_file='configs/bcube_demo.yaml')
    luigi.build([w], local_scheduler=True)
