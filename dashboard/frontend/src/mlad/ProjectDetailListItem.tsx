import React from 'react';
import styles from './ProjectDetailListItem.module.css';

interface ProjectDetailListItemProps {
	name: string;
	value: JSX.Element | string;
}

/*
* ProjectDetail view에서 각 항목을 보여주는 view
*/
export default function ProjectDetailListItem(props: ProjectDetailListItemProps) {
	const { name, value } = props;

	return <div>
		<div className={styles.container}>
			<div className={styles.name}>{name}</div>
			<div className={styles.value}>
				{value}
			</div>
		</div>
	</div>
}
