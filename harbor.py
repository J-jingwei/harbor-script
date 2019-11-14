# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : jiangjw
'''本脚本适用于清理释放harbor镜像仓库空间；
    此脚本基于harbor 1.9.0版本编写；
    harbor 1.7.0 以后版本可通过页面垃圾回收；
    如不同版本api不同需自行更改各个函数中url部分。'''

import json
import heapq
import requests
from requests.auth import HTTPBasicAuth
from tqdm import tqdm
from time import sleep



class Harbor(object):
    def __init__(self, api_url, user, num, exclude):
        """
        初始化一些基本参数
        :param auth: login password authority management
        :param head: change user-agent
        :param url: harbor server api url
        :param project_exclude: Exclude project team
        :param num_limit: Limit the number of retained versions
        :param project_special: project dict id and repo total
        :param project_state: project dict name and id
        :param repo_state: repo dict name and tag total
        :param repo_dispose: Count the number of tag processing
        :param tag_state: tag dict repo_name and tag
        """
        self.auth = user
        self.head = {"user_agent": "Mozilla/5.0"}
        self.url = api_url
        self.project_exclude = exclude
        self.num_limit = int(num)
        self.project_special = {}
        self.project_state = {}
        self.repo_state = {}
        self.repo_dispose_count = 0
        self.tag_state = {}

    def list_project(self):
        try:
            r_project = requests.get("{}/projects".format(self.url), headers=self.head)
            r_project.raise_for_status()
            # 将得到的文本转换格式
            project_data = json.loads(r_project.text)
            for i in project_data:
                # 项目组名称
                project_name = i.get('name')
                # 项目组id
                project_id = i.get('project_id')
                # 项目组仓库
                project_repo = i.get('repo_count')
                # 利用一个字典将项目名称与id对应起来
                self.project_state[project_name] = project_id
                # 由于请求现在，另外用一个字典,对应id于repo总数
                self.project_special[project_id] = project_repo
                print("\033[0;32m项目名称:{}\t项目编号:{}\t项目下仓库统计:{}\033[0m".format(project_name, project_id, project_repo))
            print("\033[0;36mproject:项目组对应id列表:{}\033[0m".format(self.project_state))
            print("\033[0;36mproject:项目id对应仓库数:{}\033[0m".format(self.project_special))
        except:
            return "list project failed."

    def list_repo(self):
        try:
            for a in self.project_state.keys():
                # 排除部分项目组
                if a not in self.project_exclude:
                    id = self.project_state.get(a)
                    # print(id)
                    # 由于请求现在，得出需请求的次数，整除+1
                    number = self.project_special.get(id) // 100 + 1
                    for i in range(number):
                        page = i + 1
                        r_repo = requests.get(
                            "{}/repositories?project_id={}&page={}&page_size=100".format(self.url, id, page),
                            headers=self.head)
                        # 将得到的文本结果转换格式
                        repo_data = json.loads(r_repo.text)
                        for r in repo_data:
                            repo_id = r.get('id')
                            repo_name = r.get('name')
                            tag_count = r.get('tags_count')
                            # 利用字典将仓库名称与tag总量对应起来
                            self.repo_state[repo_name] = tag_count
            print("\033[0;31mrepo:排除部分项目组后，需过滤处理的仓库总量为:{}\033[0m".format(len(self.repo_state)))

        except:
            return "list repo failed."

    def list_tag(self):
        try:
            # n 为repo 仓库名字
            for n in self.repo_state.keys():
                # 如果该仓库下版本总数大于数量限制，继续往下走
                if self.repo_state.get(n) > self.num_limit:
                    r_tag = requests.get('{}/repositories/{}/tags'.format(self.url, n))
                    r_tag.raise_for_status()
                    tag_data = json.loads(r_tag.text)
                    tag_dict = {}
                    for t in tag_data:
                        # 取出各个tag的名字
                        tag_name = t.get('name')
                        # 切分各个tag，取出日期时间部分
                        tag_time = int(tag_name.split('.')[-1])
                        # 将tag名称与切割出来的时间部分对应起来
                        tag_dict[tag_time] = tag_name
                    tagtime_list = []
                    tagname_list = []
                    for h in tag_dict.keys():
                        tagtime_list.append(h)
                    # 取出时间最大值三个
                    max_limit = heapq.nlargest(3, tagtime_list)
                    # 取反，将key不为这三个的value版本号找出来
                    for q in tag_dict.keys():
                        if q not in max_limit:
                            name = tag_dict.get(q)
                            tagname_list.append(name)
                    self.tag_state[n] = tagname_list
                    self.repo_dispose_count += len(tagname_list)
            print("\033[0;31mtag:本次过滤出需处理涉及仓库共:{}个，涉及删除镜像版本共:{}个\033[0m".format(len(self.tag_state),
                                                                                self.repo_dispose_count))
        except:
            return "list tag failed."

    def del_tag(self):
        try:
            if self.repo_dispose_count == 0:
                print("\033[0;34mdel:本次无需删除tag\033[0m")
            else:
                print("\033[0;34mdel:删除tag阶段耗时较长:请耐心等待\033[0m")
                pbar1 = tqdm(total=self.repo_dispose_count, unit='个', unit_scale=True)
                # na 为repo 名称
                for na in self.tag_state:
                    # ta为需删除的tag版本号
                    for ta in self.tag_state[na]:
                        r_del = requests.delete('{}/repositories/{}/tags/{}'.format(self.url, na, ta), headers=self.head,
                                                auth=self.auth)
                        r_del.raise_for_status()
                        pbar1.update(1)
                sleep(3)
                pbar1.close()
                print("\033[0;34mdel:需删除镜像已完成删除！ 共删除版本数量:{}个\033[0m".format(self.repo_dispose_count))
        except:
            return "delete tag failed."

    def volume_recycle(self):
        try:
            if self.repo_dispose_count == 0:
                print("\033[0;35mvolume:本次无需清理存储\033[0m")
            else:
                # 定义一个立即执行垃圾清理的json
                da = {"schedule": {"cron": "Manual", "type": "Manual"}}
                print("\033[0;35mvolume:开始回收存储空间！\033[0m")
                r_volume = requests.post('{}/system/gc/schedule'.format(self.url), json=da, auth=self.auth)
                r_volume.raise_for_status()
                print("\033[0;35mvolue:回收存储空间已完成！\033[0m")
        except:
            return "volume recycle failed."


def main(api_url, login, num, exclude):
    # begin开始
    har = Harbor(api_url=api_url, user=login, num=num, exclude=exclude)
    # 列出项目组
    har.list_project()
    # 列出repo仓库
    har.list_repo()
    # 列出tag版本
    har.list_tag()
    # 删除不保留版本
    har.del_tag()
    # 回收存储
    har.volume_recycle()
    print("所有操作运行完成！")


if __name__ == '__main__':
    # harbor api interface
    api_url = "https://xxx.xxx.xxx/api"  # xxx.xxx.xxx部分自行更换为harbor首页url
    # Login ,change username and password
    login = HTTPBasicAuth('username', 'password')   # 自行更改用户名，密码
    # 需要排除的项目组，自行根据情况更改，或为空
    exclude = ['xxx', 'yyy', 'zzz']    # 自行更改需排除项目组，也可以删除为空; 例:exclude = ['k8s', 'basic', 'library']
    # 仓库下版本过多，需保留的最近版本数量
    keep_num = 3
    # 启动Start the engine
    main(api_url=api_url, login=login, num=keep_num, exclude=exclude)
