import React from 'react';
import styles from './ProjectDetailListItem.module.css';

interface ProjectDetailListItemProps {
	name: string;
	value: JSX.Element | string;
}

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
