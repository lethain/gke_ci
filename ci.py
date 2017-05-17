"""
Simple Google PubSub queue consumer to update Kubernetes.
"""
import argparse
import pprint
import time
import json
import requests
from collections import defaultdict
from google.cloud import pubsub


"""
{"id":"c5c37ac1-e89b-44f1-ada8-edf41711dd9a","projectId":"larson-deployment","status":"WORKING",
"source":{"repoSource":{"projectId":"larson-deployment","repoName":"daedalus","branchName":"master"}},
"steps":[{"name":"gcr.io/cloud-builders/docker","args":["build","-t","gcr.io/larson-deployment/daedalus:c4efe3da9ff9f2a2d146026eac92ad657dd0479a","."]}],
"createTime":"2017-05-15T04:38:36.122991Z","startTime":"2017-05-15T04:38:39.405707Z","timeout":"600.000s",
"images":["gcr.io/larson-deployment/daedalus:c4efe3da9ff9f2a2d146026eac92ad657dd0479a"],
"logsBucket":"gs://342196402007.cloudbuild-logs.googleusercontent.com",
"sourceProvenance":{"resolvedRepoSource":{"projectId":"larson-deployment","repoName":"daedalus","commitSha":"c4efe3da9ff9f2a2d146026eac92ad657dd0479a"}},
"buildTriggerId":"c1add629-8dbe-4e9e-9c51-c0824842f974",
"logUrl":"https://console.cloud.google.com/gcr/builds/c5c37ac1-e89b-44f1-ada8-edf41711dd9a?project=larson-deployment"}
{u'buildId': u'c5c37ac1-e89b-44f1-ada8-edf41711dd9a', u'status': u'WORKING'}
"""


def handle(msg, loc, ignore):
    print msg.attributes
    data = json.loads(msg.data)
    status = msg.attributes['status']
    logUrl = data['logUrl']
    images = data['images']
    repo = data['source']['repoSource']['repoName']
    kub = build_k8s_cli(loc)    
    if status == 'SUCCESS':
        print "[%s] Build succeeded." % (repo,)
        deps = deployments(kub, ignore)
        print "[%s] Found deployments: %s." % (repo, deps)
        for image in images:
            print "[%s] Updated %s." % (repo, image)
            wo_tag = container_without_tag(image)
            for dep_cont, dep_link in deps.iteritems():
                if wo_tag == dep_cont:
                    print "YES DEPLOY: %s, %s, %s" % (wo_tag, dep_cont, dep_link)
                    # kubectl patch deployment deployment-example -p '{"spec":{"template":{"spec":{"containers":[{"name":"nginx","image":"nginx:1.11"}]}}}}'
                    # figure out... some way to do this
                else:
                    print "NO, DO NOTDEPLOY: %s, %s, %s" % (wo_tag, dep_cont, dep_link)


def container_without_tag(con_str):
    "Return container URL without the tag or preceding colon."
    return ':'.join(con_str.split(':')[:-1])


def deployments(cli, ignore):
    container_dep = defaultdict(list)
    deps = cli('/apis/extensions/v1beta1/deployments').json()['items']
    for dep in deps:
        name = dep['metadata']['name']
        if dep['metadata']['namespace'] in ignore:
            continue

        print 'found deployment: %s' % (name,)
        containers = dep['spec']['template']['spec']['containers']
        for container in containers:
            img = container_without_tag(container['image'])
            container_dep[img].append(dep['metadata']['selfLink'])
    return container_dep


def build_k8s_cli(loc):
    s = requests.Session()
    s.verify = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    return lambda path : s.get("%s%s" % (loc, path))


def run(loc, project, ignore, delay):
    "Loop endlessly checking for builds."
    client = pubsub.Client()
    topic = client.topic('cloud_builds')
    s = pubsub.subscription.Subscription('gke_ci', topic=topic)
    while True:
        pulled = s.pull(max_messages=10)
        for ack_id, message in pulled:
            try:
                handle(message, loc, ignore)
            finally:
                s.acknowledge([ack_id])
        time.sleep(delay)



def main():
    p = argparse.ArgumentParser(description='Continuous integration for GKE.')
    p.add_argument('project', help='name of GCE project')
    p.add_argument('--loc', default='https://kubernetes', help='location to access Kubernetes API')
    p.add_argument('--delay', type=int, default=1.0, help='delay between checking for messages')
    p.add_argument('--ignore', default='kube-system', help='csv of namespaces to ignore')
    args = p.parse_args()
    run(args.loc, args.project, args.ignore.split(','), args.delay)


if __name__ == "__main__":
    main()
