import React, { useContext } from 'react';
import { Tabs } from 'antd';
import NodeList from '../mlad/NodeList';
import { Node, Project, ProjectSpec } from '../mlad/models';
import ProjectList from '../mlad/ProjectList';
import useFetchSocket from './useFetchSocket';
import { GlobalContext } from '../App';

const { TabPane } = Tabs;


export default function MLADContainer() {

	const context = useContext(GlobalContext);
	const node_url = `${context.baseurl}/nodes`;
	const project_url = `${context.baseurl}/projects`;
	const detail_url = `${context.baseurl}/project`;
	const { data: nodes } = useFetchSocket<Node>(node_url, Node);
	const { data: projects } = useFetchSocket<Project>(project_url, Project);
	const { data: projectSpec, setRequestData }
		= useFetchSocket<ProjectSpec>(detail_url, ProjectSpec);

	return <>
		<Tabs defaultActiveKey='1'>
			<TabPane tab='Projects' key='1'>
				<ProjectList
					projects={projects as Project[]}
					projectSpec={projectSpec as ProjectSpec}
					setRequestData={setRequestData} />
			</TabPane>
			<TabPane tab='Nodes' key='2'>
				<NodeList nodes={nodes as Node[]} />
			</TabPane>
		</Tabs>
	</>
}
