pipeline {
    agent {
        docker {
            image 'python:3.11'
            args '-u root -v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git submodule update --init --recursive'
            }
        }

        stage('Init') {
            steps {
                sh '''
                    if ! command -v pipenv >/dev/null 2>&1; then
                        python3 -m ensurepip --upgrade || true
                        python3 -m pip install --user --upgrade pip setuptools wheel
                        python3 -m pip install --user pipenv
                        export PATH="$HOME/.local/bin:$PATH"
                    fi
                    command -v pipenv
                '''
                sh '''
                    export PATH="$HOME/.local/bin:$PATH"
                    PIPENV_PIPFILE=config/Pipfile pipenv install --dev
                '''
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

        stage('E2E Tests') {
            steps {
                sh 'make e2e-up'
                sh 'make e2e-test'
            }
            post {
                always {
                    sh 'make e2e-logs || true'
                    sh 'make e2e-down || true'
                }
            }
        }

        stage('E2E Fabric Tests') {
            steps {
                sh 'docker network create fabric_drone 2>/dev/null || true'
                sh '''
                    cd fabric-network
                    ./start.sh up
                '''
                sh '''
                    ENABLE_FABRIC_LEDGER=true make e2e-up
                '''
                sh '''
                    docker compose -f systems/dummy_fabric/docker-compose.yml --profile fabric --profile kafka up -d --build
                '''
                sh '''
                    ENABLE_FABRIC_LEDGER=true PIPENV_PIPFILE=config/Pipfile \
                    pipenv run pytest tests/e2e/test_e2e_fabric_scenario.py -v -s --tb=short
                '''
            }
            post {
                always {
                    sh 'docker compose -f systems/dummy_fabric/docker-compose.yml --profile fabric --profile kafka logs --no-color || true'
                    sh 'docker compose -f systems/dummy_fabric/docker-compose.yml --profile fabric --profile kafka down || true'
                    sh '''
                        cd fabric-network
                        ./start.sh down || true
                    '''
                    sh 'make e2e-down || true'
                }
            }
        }
    }

    post {
        always {
            sh 'make docker-down || true'
            sh '''
                for sys in systems/*/; do
                    [ -f "$sys/Makefile" ] && make -C "$sys" docker-down PROJECT_ROOT="$(pwd)" 2>/dev/null || true
                done
            '''
        }
    }
}
