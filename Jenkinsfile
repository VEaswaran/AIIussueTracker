// =============================================================================
// AI Issue Tracker MCP — Jenkins Declarative Pipeline
//
// Stages:
//   1. Checkout
//   2. Build & Test  (Maven — mvn clean verify)
//   3. Code Quality  (SonarQube — skipped if SONAR_HOST_URL not set)
//   4. Package       (fat JAR via spring-boot-maven-plugin)
//   5. Deploy        (SSH deploy to target server — skipped if DEPLOY_HOST not set)
//
// Docker stages removed — add back when registry is ready.
//
// Required Jenkins Credentials:
//   - DEPLOY_SSH_CREDENTIALS : SSH key for deployment server (id: deploy-ssh-key)
//
// Optional Environment Variables:
//   - DEPLOY_HOST     : e.g. 10.0.0.5   (leave blank to skip deploy)
//   - DEPLOY_USER     : e.g. ubuntu
//   - DEPLOY_PATH     : e.g. /opt/ai-issue-tracker
//   - SONAR_HOST_URL  : SonarQube server URL
//   - SONAR_TOKEN     : SonarQube auth token
// =============================================================================

pipeline {

    agent any

    // -------------------------------------------------------------------------
    // Tool versions (must match names configured in Jenkins → Global Tool Config)
    // -------------------------------------------------------------------------
    tools {
        jdk   'JDK-17'
        maven 'Maven-3.9'
    }

    // -------------------------------------------------------------------------
    // Pipeline-wide environment
    // -------------------------------------------------------------------------
    environment {
        APP_NAME        = 'ai-issue-tracker-mcp'
        APP_VERSION     = '1.0.0'
        JAR_NAME        = "${APP_NAME}-${APP_VERSION}.jar"
        // Docker env vars removed — add back when Docker registry is ready
        // DOCKER_IMAGE = "${APP_NAME}"
        // IMAGE_TAG    = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}".replaceAll('/', '-')
        // DOCKER_CREDS = credentials('docker-registry-creds')
    }

    // -------------------------------------------------------------------------
    // Build options
    // -------------------------------------------------------------------------
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    // -------------------------------------------------------------------------
    // Trigger: poll SCM every 5 min + GitHub webhook
    // -------------------------------------------------------------------------
    triggers {
        pollSCM('H/5 * * * *')
    }

    // =========================================================================
    // STAGES
    // =========================================================================
    stages {

        // ---------------------------------------------------------------------
        stage('Checkout') {
        // ---------------------------------------------------------------------
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    echo "Branch: ${env.BRANCH_NAME} | Commit: ${env.GIT_COMMIT_SHORT}"
                }
            }
        }

        // ---------------------------------------------------------------------
        stage('Guard — No Direct Push to main') {
        // ---------------------------------------------------------------------
        // CHANGE_ID is only set by the GitHub Branch Source plugin when the
        // build was triggered by a Pull Request.  If it is missing and we are
        // on the main branch then someone pushed directly — reject it.
            steps {
                script {
                    if (env.BRANCH_NAME == 'main' && !env.CHANGE_ID) {
                        error("""
╔══════════════════════════════════════════════════════════════╗
║  ❌  DIRECT PUSH TO main IS NOT ALLOWED                      ║
║                                                              ║
║  Please open a Pull Request from your feature branch.        ║
║  Direct commits to main are rejected by CI policy.           ║
╚══════════════════════════════════════════════════════════════╝
                        """)
                    }
                    if (env.BRANCH_NAME == 'main') {
                        echo "✅ Build triggered by PR #${env.CHANGE_ID} — proceeding."
                    }
                }
            }
        }

        // ---------------------------------------------------------------------
        stage('Build & Test') {
        // ---------------------------------------------------------------------
            steps {
                sh '''
                    mvn clean verify \
                        -Dmock.enabled=true \
                        --batch-mode \
                        --no-transfer-progress
                '''
            }
            post {
                always {
                    // Publish JUnit test results
                    junit allowEmptyResults: true,
                          testResults: '**/target/surefire-reports/*.xml'

                    // Publish JaCoCo coverage report (if present)
                    jacoco(
                        execPattern:    '**/target/jacoco.exec',
                        classPattern:   '**/target/classes',
                        sourcePattern:  '**/src/main/java',
                        skipCopyLocalLib: true
                    )
                }
            }
        }

        // ---------------------------------------------------------------------
        stage('Code Quality — SonarQube') {
        // ---------------------------------------------------------------------
            // Skip this stage if SONAR_HOST_URL is not configured
            when {
                expression { return env.SONAR_HOST_URL?.trim() }
            }
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '''
                        mvn sonar:sonar \
                            -Dsonar.projectKey=${APP_NAME} \
                            -Dsonar.projectName="${APP_NAME}" \
                            -Dsonar.projectVersion=${APP_VERSION} \
                            --batch-mode \
                            --no-transfer-progress
                    '''
                }
                // Wait for Quality Gate result (fails build if gate fails)
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        // ---------------------------------------------------------------------
        stage('Package') {
        // ---------------------------------------------------------------------
            steps {
                sh '''
                    mvn package -DskipTests \
                        --batch-mode \
                        --no-transfer-progress
                '''
                archiveArtifacts artifacts: "target/${JAR_NAME}",
                                 fingerprint: true,
                                 allowEmptyArchive: false
                echo "JAR packaged: target/${JAR_NAME}"
            }
        }

        // Docker Build and Docker Push stages removed — add back when Docker registry is ready
        // See jenkins/Dockerfile for the image definition

        // ---------------------------------------------------------------------
        stage('Deploy') {
        // ---------------------------------------------------------------------
            when {
                allOf {
                    branch 'main'
                    expression { return env.DEPLOY_HOST?.trim() }
                }
            }
            steps {
                sshagent(credentials: ['deploy-ssh-key']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "mkdir -p ${DEPLOY_PATH}"

                        scp -o StrictHostKeyChecking=no \
                            target/${JAR_NAME} \
                            jenkins/deploy/start.sh \
                            ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/

                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "chmod +x ${DEPLOY_PATH}/start.sh && \
                             ${DEPLOY_PATH}/start.sh ${DEPLOY_PATH}/${JAR_NAME}"
                    """
                }
            }
        }

    }
    // end stages

    // =========================================================================
    // POST
    // =========================================================================
    post {

        success {
            echo "✅ Pipeline SUCCESS — ${APP_NAME}:${IMAGE_TAG}"
        }

        failure {
            echo "❌ Pipeline FAILED — check logs above"
            // Uncomment to send email on failure:
            // mail to: 'team@yourcompany.com',
            //      subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
            //      body:    "See ${env.BUILD_URL}"
        }

        always {
            // Docker cleanup removed — add back when Docker is enabled
            cleanWs()
        }
    }

}

