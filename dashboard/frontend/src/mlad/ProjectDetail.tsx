import { Divider } from 'antd';
import React, { useMemo } from 'react';
import YAMLEditor from './YAMLEditor';
import styles from './ProjectDetail.module.css';
import ProjectDetailSubtitle from './ProjectDetailSubtitle';
import ProjectDetailListItem from './ProjectDetailListItem';
import AppDetail from './AppDetail';
import { ProjectSpec } from './models';


const obtainSummaryData = (projectSpec: ProjectSpec) => {
	return [
		{ key: 'Age', value: projectSpec.age },
		{ key: 'Name', value: projectSpec.name },
		{ key: 'User Name', value: projectSpec.userName },
		{ key: 'Image', value: projectSpec.image },
		{ key: 'Namespace', value: projectSpec.namespace },
		{ key: 'Version', value: projectSpec.version },
		{ key: 'Hostname', value: projectSpec.hostname },
		{ key: 'Project Path', value: projectSpec.projectPath},
		{ key: 'CPU (Cores)', value: projectSpec.cpu },
		{ key: 'GPU (#)', value: projectSpec.gpu },
		{ key: 'Memory (MB)', value: projectSpec.mem },
	];
}


interface ProjectDetailProps {
	projectSpec: ProjectSpec;
}

export default function ProjectDetail({ projectSpec }: ProjectDetailProps) {

	const summaryData = useMemo(() => obtainSummaryData(projectSpec), [projectSpec]);

	return <div className={styles.projectDetailContainer}>
		<ProjectDetailSubtitle title={'Project Summary'} />
		<Divider plain >Summary</Divider>
		{summaryData.map(d => <ProjectDetailListItem key={d.key} name={d.key} value={d.value}/>)}
		<Divider plain >Project File</Divider>
		<YAMLEditor data={projectSpec.yaml} />
		<ProjectDetailSubtitle title={'Apps'} />
		{projectSpec.appSpecs.map(spec => <AppDetail spec={spec} key={spec.name}/>)}
	</div>
}
