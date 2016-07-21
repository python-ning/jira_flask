# encoding=utf-8
from flask import *
from config import *
app = Flask(__name__)


@app.route('/create_cloud_server', methods=['GET', 'POST'])
def create_cloud_server():
    network_fields = ''
    create_cloud_server_field = json.loads(request.data)['issue']['fields']
    create_cloud_server_status = create_cloud_server_field['status']['name']
    comments_field = json.loads(request.data)['issue']['key']
    for field in create_cloud_server_field[params['network']]:
        network_fields += (str(field['value']) + ',')
    is_status = create_cloud_server_field[params['status']]
    server_params = {
        'token': token,
        'name': create_cloud_server_field[params['csname']],
        'hostname': create_cloud_server_field[params['hostname']],
        'password': create_cloud_server_field[params['root_password']],
        'image': create_cloud_server_field[params['image']]['value'],
        'cpu': int(create_cloud_server_field[params['cpu']]),
        'memory': int(create_cloud_server_field[params['memory']]),
        'disk': int(create_cloud_server_field[params['disk']]),
        'comments': create_cloud_server_field[params['comments']],
        'network': network_fields[:-1],
        'datacenter': create_cloud_server_field[params['datacenter']]['value'],
        'bandwidth': int(create_cloud_server_field[params['bandwidth']]),
    }
    if create_cloud_server_status == 'Done':
        if is_status == 'no':
            status_data = json.dumps({"fields": {str(params['status']): "yes"}})
            url = 'http://localhost:8081/rest/api/2/issue/%s' % comments_field
            response = requests.put(url, headers=HEADERS, data=status_data, auth=AUTH)
            api_obj.provision(server_params)
            comment = add_comments_field(comments_field, '创建云主机成功')
    return 'create_cloud_server!'


@app.route('/add_cloud_volume', methods=['GET', 'POST'])
def create_cloud_volume():
    # print request.data
    comments_field = json.loads(request.data)['issue']['key']
    create_cloud_volume_field = json.loads(request.data)['issue']['fields']
    is_status = create_cloud_volume_field[params['status']]
    create_cloud_volume_status = create_cloud_volume_field['status']['name']
    customfield_datacenter_value = create_cloud_volume_field[params['datacenter']]['value']
    customfield_size_value = int(create_cloud_volume_field[params['size']])
    customfield_tags_value = create_cloud_volume_field[params['tags']]
    if create_cloud_volume_status == 'Done':
        if is_status == 'no':
            status_data = json.dumps({"fields": {str(params['status']): "yes"}})
            url = 'http://localhost:8081/rest/api/2/issue/%s' % comments_field
            response = requests.put(url, headers=HEADERS, data=status_data, auth=AUTH)
            api_obj.create_volume(customfield_datacenter_value, customfield_size_value, customfield_tags_value, cluster=None, ioparams={})
            comment = add_comments_field(comments_field, '创建云硬盘成功')
    return 'add_cloud_volume!'


def add_comments_field(comments_field, data):
    post_comments_url = "%s/rest/api/2/issue/%s/comment" % (HOSTNAME, comments_field)
    comments = requests.post(post_comments_url, data='{"body":"%s"}' % data, headers=HEADERS, auth=AUTH)
    return comments


if __name__ == '__main__':
    app.run()
