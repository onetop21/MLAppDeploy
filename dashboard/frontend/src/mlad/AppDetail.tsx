import React from 'react';
import EnvView from './EnvView';
import { AppSpec, TaskSpec } from './models';
import ProjectDetailListItem from './ProjectDetailListItem';

import styles from './AppDetail.module.css';
import ExposeItem from './ExposeItem';


const getTaskView = (task: TaskSpec) => {
	return <div key={task.name}>
		<div className={styles.taskName}>
			<svg width='16' height='16' style={{marginRight: '0.3rem'}}>
				<circle cx='8' cy='8' r='4' fill={task.phase === 'Running' ? 'green' : 'red'} />
			</svg>
			{task.name}
		</div>
		<ProjectDetailListItem name='node' value={task.nodeName} />
		<ProjectDetailListItem name='phase' value={task.phase} />
		<ProjectDetailListItem name='CPU (Cores)' value={task.cpu} />
		<ProjectDetailListItem name='GPU (#)' value={task.gpu} />
		<ProjectDetailListItem name='Memory (MB) ' value={task.mem} />
	</div>
}

interface ServiceDetailProps {
	spec: AppSpec;
}
/**
 * Detail drawer에서 App의 자세한 상태를 나타내는 view
 */
export default function AppDetail({ spec }: ServiceDetailProps) {

	return <>
		<div className={styles.serviceName}>
			<svg width='16' height='16' style={{marginRight: '0.3rem'}}>
				<circle cx='8' cy='8' r='5' fill={spec.statusColor} />
			</svg>
			{spec.name}
		</div>
		<ProjectDetailListItem name='status' value={spec.status} />
		<ProjectDetailListItem name='environments' value={<EnvView env={spec.env} />} />
		<ProjectDetailListItem name='CPU (Cores)' value={spec.cpu} />
		<ProjectDetailListItem name='GPU (#)' value={spec.gpu} />
		<ProjectDetailListItem name='Memory (MB)' value={spec.mem} />
		{spec.taskSpecs.map(taskSpec => getTaskView(taskSpec))}
    <ExposeItem exposes={spec.exposes} />
	</>
}
