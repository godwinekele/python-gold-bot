pipeline {
    agent any
    
    environment {
        // GitHub Repository
        GITHUB_REPO = 'https://github.com/godwinekele/python-gold-bot.git'
        GITHUB_CREDENTIALS = 'github-cred'  // Set in Jenkins
        
        // Docker Hub Configuration
        DOCKER_HUB_CREDENTIALS = 'dockerhub-cred'  // Set in Jenkins
        DOCKER_HUB_REPO = 'godwinekele/godwin-bot'
        
        // Image Tags
        DOCKER_TAG = "${BUILD_NUMBER}"
        CONTAINER_NAME = 'gold_scalper_bot'
        
        // Port Configuration
        WEB_PORT = '4000'
    }
    
    stages {
        stage('Checkout from GitHub') {
            steps {
                echo '📥 Cloning repository from GitHub...'
                git branch: 'main',
                    credentialsId: "${GITHUB_CREDENTIALS}",
                    url: "${GITHUB_REPO}"
                
                echo '✅ Code checked out successfully'
            }
        }
        
        stage('Verify Environment Files') {
            steps {
                script {
                    echo '🔍 Checking for .env file...'
                    
                    if (!fileExists('.env')) {
                        error('❌ .env file not found! Please create it with MT5 credentials.')
                    }
                    
                    echo '✅ Environment files verified'
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    echo "🔨 Building Docker image: ${DOCKER_HUB_REPO}:${DOCKER_TAG}"
                    
                    // Build image
                    sh """
                        docker build \
                            --tag ${DOCKER_HUB_REPO}:${DOCKER_TAG} \
                            --tag ${DOCKER_HUB_REPO}:latest \
                            .
                    """
                    
                    echo '✅ Docker image built successfully'
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                script {
                    echo '📤 Pushing image to Docker Hub...'
                    
                    // Login and push to Docker Hub
                    withCredentials([usernamePassword(
                        credentialsId: "${DOCKER_HUB_CREDENTIALS}",
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            echo ${DOCKER_PASS} | docker login -u ${DOCKER_USER} --password-stdin
                            docker push ${DOCKER_HUB_REPO}:${DOCKER_TAG}
                            docker push ${DOCKER_HUB_REPO}:latest
                        """
                    }
                    
                    echo '✅ Image pushed to Docker Hub'
                }
            }
        }
        
        stage('Stop Old Container') {
            steps {
                script {
                    echo '🛑 Stopping old container if exists...'
                    sh """
                        docker stop ${CONTAINER_NAME} 2>/dev/null || true
                        docker rm ${CONTAINER_NAME} 2>/dev/null || true
                    """
                    echo '✅ Old container removed'
                }
            }
        }
        
        stage('Deploy New Container') {
            steps {
                script {
                    echo '🚀 Deploying new container...'
                    
                    sh """
                        docker run -d \
                            --name ${CONTAINER_NAME} \
                            -p ${WEB_PORT}:${WEB_PORT} \
                            --env-file .env \
                            -v \$(pwd)/logs:/app/logs \
                            --restart unless-stopped \
                            ${DOCKER_HUB_REPO}:latest
                    """
                    
                    echo '✅ Container deployed successfully'
                }
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    echo '🏥 Performing health check...'
                    
                    // Wait for container to start
                    sleep(time: 15, unit: 'SECONDS')
                    
                    // Check if container is running
                    def containerStatus = sh(
                        script: "docker ps --filter name=${CONTAINER_NAME} --format '{{.Status}}'",
                        returnStdout: true
                    ).trim()
                    
                    if (!containerStatus.contains('Up')) {
                        error("❌ Container is not running!")
                    }
                    
                    // Check web UI
                    def httpStatus = sh(
                        script: "curl -s -o /dev/null -w '%{http_code}' http://localhost:${WEB_PORT}",
                        returnStdout: true
                    ).trim()
                    
                    if (httpStatus != '200') {
                        error("❌ Web UI health check failed with status: ${httpStatus}")
                    }
                    
                    echo '✅ Health check passed - Bot is running!'
                }
            }
        }
        
        stage('Display Access Info') {
            steps {
                script {
                    echo """
                    ╔════════════════════════════════════════════════════╗
                    ║          🎉 DEPLOYMENT SUCCESSFUL 🎉               ║
                    ╠════════════════════════════════════════════════════╣
                    ║ Container Name: ${CONTAINER_NAME}                  ║
                    ║ Web Dashboard:  http://YOUR_SERVER_IP:${WEB_PORT}  ║
                    ║ Docker Image:   ${DOCKER_HUB_REPO}:${DOCKER_TAG}   ║
                    ║ Build Number:   ${BUILD_NUMBER}                    ║
                    ╚════════════════════════════════════════════════════╝
                    """
                }
            }
        }
        
        stage('Cleanup Old Images') {
            steps {
                script {
                    echo '🧹 Cleaning up old Docker images...'
                    
                    sh """
                        # Keep only last 5 builds
                        docker images ${DOCKER_HUB_REPO} --format '{{.Tag}}' | \
                        grep -E '^[0-9]+\$' | \
                        sort -rn | \
                        tail -n +6 | \
                        xargs -r -I {} docker rmi ${DOCKER_HUB_REPO}:{} 2>/dev/null || true
                    """
                    
                    echo '✅ Cleanup completed'
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Pipeline executed successfully!'
            echo '📊 View logs: docker logs -f ${CONTAINER_NAME}'
            
            // Optional: Send email notification
            // emailext (
            //     subject: "✅ Build #${BUILD_NUMBER} - SUCCESS",
            //     body: "Trading bot deployed successfully!",
            //     to: "godwinekele19@gmail.com"
            // )
        }
        
        failure {
            echo '❌ Pipeline failed! Check logs for details.'
            
            // Stop and remove failed container
            sh """
                docker stop ${CONTAINER_NAME} 2>/dev/null || true
                docker rm ${CONTAINER_NAME} 2>/dev/null || true
            """
            
            // Optional: Send failure notification
            // emailext (
            //     subject: "❌ Build #${BUILD_NUMBER} - FAILED",
            //     body: "Deployment failed. Check Jenkins console.",
            //     to: "godwinekele19@gmail.com"
            // )
        }
        
        always {
            echo '🧹 Performing cleanup...'
            
            // Clean up Docker login
            sh 'docker logout || true'
        }
    }
}
