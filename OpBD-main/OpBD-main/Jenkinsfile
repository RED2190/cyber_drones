pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Init') {
            steps {
                sh 'command -v pipenv >/dev/null 2>&1 || pip install pipenv'
                sh 'PIPENV_PIPFILE=config/Pipfile pipenv install --dev'
            }
        }

        stage('Unit Tests') {
            steps {
                sh 'make ci-unit-test'
            }
        }

        stage('Integration Tests') {
            steps {
                sh 'make ci-integration-test'
            }
        }
    }

    post {
        always {
            sh 'make docker-down || true'
            sh 'for sys in systems/*/; do [ -f "$sys/Makefile" ] && make -C "$sys" docker-down 2>/dev/null || true; done'
        }
    }
}
