import React, { useContext, useState } from 'react';
import './App.css';
import { Layout, Menu } from 'antd';
import { PieChartOutlined } from '@ant-design/icons';
import { Link, Redirect, Route, Switch } from 'react-router-dom';
import MLADContainer from './containers/MLADContainer';
import ComponentContainer from './containers/ComponentContainer';
import useFetchSocket from './containers/useFetchSocket';

const { Content, Sider } = Layout;

class BoardComponent {
	name: string;
	appName: string;
	hosts: string[];

	constructor(raw: any) {
		this.name = raw['name'];
		this.appName = raw['app_name'];
		this.hosts = raw['hosts'];
	}

	get pages() {
		return this.hosts.map(host => {
			const port = host.split(':')[2]
			const key = `${this.appName}-${port}`
			return { name: this.name, appName: this.appName, host, port, key };
		});
	}

	get raw() {
		return {
			'name': this.name,
			'app_name': this.appName,
			'hosts': this.hosts
		};
	}
};

export const GlobalContext = React.createContext<{
	baseurl: string
}>({ baseurl: `ws://${window.location.host}/mlad`});

// export const GlobalContext = React.createContext<{
// 	baseurl: string
// }>({ baseurl: `ws://localhost:2022/mlad`});

function App() {

  const [collapsed, setCollapsed] = useState(false);
	const context = useContext(GlobalContext);
	const url = `${context.baseurl}/components`;
	const { data: components } = useFetchSocket<BoardComponent>(url, BoardComponent);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible
        theme='dark'
        collapsed={collapsed}
        onCollapse={() => setCollapsed(collapsed => !collapsed)}
      >
        <div className='logo'>
          <img src='/logo.png' alt='logo' />
        </div>
        <Menu theme='dark' defaultSelectedKeys={['1']}>
          <Menu.Item key='1' icon={<PieChartOutlined />}>
						<Link to={{pathname: '/mlad'}}>
            	COMMON
						</Link>
          </Menu.Item>
					{(components as BoardComponent[]).map((component) => {
						return component.pages.map(page => {
							return <Menu.Item key={`${page.key}`} icon={<PieChartOutlined />}>
								<Link to={{pathname: `/${page.key}`}}>
									{page.key}
								</Link>
							</Menu.Item>
						});
					})}
        </Menu>
      </Sider>
      <Layout>
        <Content>
          <Switch>
						<Redirect exact from='/' to='/mlad' />
            <Route exact path='/mlad'>
							<div className='container'>
              	<MLADContainer />
							</div>
            </Route>
						{(components as BoardComponent[]).map(component => {
							return component.pages.map(page => {
								return <Route exact path={`/${page.key}`} key={page.key}>
									<ComponentContainer host={page.host} />
								</Route>
							})
						})}
          </Switch>
        </Content>
      </Layout>
    </Layout>
  );
}

export default App;
