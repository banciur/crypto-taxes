import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Badge from 'react-bootstrap/Badge';
import styles from "./page.module.css";

const Home = () => (
    <Container fluid>
        <Row>
            <Col> <Badge bg="secondary">1 of 3</Badge></Col>
            <Col>2 of 3</Col>
            <Col>3 of 3</Col>
        </Row>
    </Container>
);

export default Home;
