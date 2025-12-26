pipeline {
    agent any

    environment {
        DOCKERTAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Cleanup workspace') {
            steps {
                cleanWs()
            }
        }

        stage('Checkout from GitHub') {
            steps {
                git branch: 'main',
                    credentialsId: 'github',
                    url: 'https://github.com/godwinekele/update-manifest.git'
            }
        }

        stage('Update Manifest Repo') {
            steps {
                script {
                    catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                        withCredentials([
                            usernamePassword(
                                credentialsId: 'github',
                                usernameVariable: 'GIT_USERNAME',
                                passwordVariable: 'GIT_PASSWORD'
                            )
                        ]) {

                            sh 'git config user.email "godwinekele@gmail.com"'
                            sh 'git config user.name "Godwin Ekele"'

                            sh 'cat deployment.yaml'

                            sh '''
                            sed -i "s+godwinekele/test-app:[^[:space:]]*+godwinekele/test-app:${DOCKERTAG}+g" deployment.yaml
                            '''

                            sh 'cat deployment.yaml'

                            sh 'git add .'
                            sh 'git commit -m "Updated image tag to ${DOCKERTAG} by Jenkins build ${BUILD_NUMBER}"'
                            sh 'git push https://${GIT_USERNAME}:${GIT_PASSWORD}@github.com/${GIT_USERNAME}/update-manifest.git HEAD:main'
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Successfully updated manifest with image tag: ${DOCKERTAG}"
        }
        failure {
            echo "Manifest update failed"
        }
    }
}

