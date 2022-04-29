import React from 'react';

interface ProjectDetailSubtitleProps {
	title: string;
}
/**
 * ProjectDetail view에서 subtitle을 표기하기 위한 view 
 */
export default function ProjectDetailSubtitle({ title }: ProjectDetailSubtitleProps) {
	return <div>
		<div style={{ fontSize: '1rem', marginBottom: '1rem'}}>{title}</div>
	</div>
}
