import luigi
from bcube_demo_pipeline import MainWorkflow
from dlib.call_solr import pull_from_solr


if __name__ == '__main__':
    # to run from the commandline
    pull_from_solr('bcube_demo/docs')
    w = MainWorkflow(doc_dir='bcube_demo/docs', yaml_file='configs/bcube_demo.yaml')
    luigi.build([w], local_scheduler=True)
