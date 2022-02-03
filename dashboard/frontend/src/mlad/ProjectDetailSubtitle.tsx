import React from 'react';

interface ProjectDetailSubtitleProps {
	title: string;
}

export default function ProjectDetailSubtitle({ title }: ProjectDetailSubtitleProps) {
	return <div>
		<div style={{ fontSize: '1rem', marginBottom: '1rem'}}>{title}</div>
	</div>
}
