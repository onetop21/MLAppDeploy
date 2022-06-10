import React, { useEffect, useMemo, useRef } from 'react';
import yamlParser from 'yaml'
import hljs from 'highlight.js/lib/core';
import 'highlight.js/styles/dark.css';
import yaml from 'highlight.js/lib/languages/yaml';

hljs.registerLanguage('yaml', yaml);

interface YAMLEditorProps {
	data: any;
}

/**
 * highlight.js의 문법을 통하여 project yaml을 그리는 view 
 */
export default function YAMLEditor({ data }: YAMLEditorProps) {

	const content = useMemo(() => (yamlParser.stringify(data)), [data]);
	const ref = useRef<HTMLElement | null>(null);

	useEffect(() => {
		hljs.highlightAll();
		if (ref.current) {
			hljs.highlightElement(ref.current);
		}
	}, [ref]);


	return <pre>
		<code
			className='yaml'
			ref={ref}>
			{content}
		</code>
	</pre>
}
