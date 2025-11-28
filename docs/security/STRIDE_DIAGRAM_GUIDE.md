# STRIDE Threat Model Diagram Guide

## 📊 Overview

This document explains the STRIDE threat model diagram for the ACME Model Registry system. The diagram visualizes all system components, trust boundaries, data flows, and security mitigations.

## 🗺️ How to View the Diagram

### Option 1: Draw.io / diagrams.net (Recommended)
1. Go to [https://app.diagrams.net/](https://app.diagrams.net/) or [https://draw.io/](https://draw.io/)
2. Click **File → Open from → Device**
3. Select `docs/security/STRIDE_Threat_Model.drawio`
4. The diagram will load with all components and STRIDE analysis

### Option 2: VS Code Extension
1. Install the "Draw.io Integration" extension in VS Code
2. Open `docs/security/STRIDE_Threat_Model.drawio`
3. The diagram will render directly in VS Code

## 🏗️ Diagram Structure

### Trust Boundaries

The diagram is organized into **6 trust boundaries**:

1. **External Clients** (Blue)
   - Users accessing the system via browser/CLI

2. **API Edge** (Green)
   - AWS WAF, API Gateway, Rate Limiting Middleware

3. **Compute Layer** (Purple)
   - ECS Fargate, FastAPI application, Routes, Services

4. **Data Storage** (Orange)
   - S3 buckets, DynamoDB tables

5. **Security Services** (Gray)
   - KMS, Secrets Manager, IAM

6. **Monitoring & Auditing** (Green)
   - CloudWatch, CloudTrail, AWS Config

### Data Flows

- **Blue solid lines**: Primary data flows (HTTPS, package data, metadata)
- **Orange dashed lines**: Security service connections (encryption keys, secrets)
- **Green dashed lines**: Monitoring/audit connections (logs, events)

## 🛡️ STRIDE Categories

The diagram includes detailed threat analysis for each STRIDE category:

### 🧩 Spoofing Identity (83.3% coverage)
- **Threat**: Forged/reused JWT tokens, impersonation
- **Mitigations**: JWT with KMS, token expiration, use-count tracking, revocation checks, IAM isolation
- **Gap**: Admin MFA not enforced

### 🧱 Tampering with Data (100% coverage)
- **Threat**: Altered packages/metadata
- **Mitigations**: SSE-KMS encryption, S3 versioning, presigned URLs, conditional writes, SHA-256 hashes

### 🧾 Repudiation (100% coverage)
- **Threat**: User denies actions
- **Mitigations**: CloudTrail, CloudWatch logs, event logging, user attribution, Glacier archiving

### 🔒 Information Disclosure (100% coverage)
- **Threat**: Unauthorized access to sensitive data
- **Mitigations**: Least-privilege IAM, presigned URLs, encryption, RBAC, security headers, log redaction

### 🧨 Denial of Service (83.3% coverage)
- **Threat**: Resource exhaustion attacks
- **Mitigations**: API Gateway throttling, WAF, rate limiting, timeouts, autoscaling, streaming uploads, ReDoS protection

### 🧍‍♂️ Elevation of Privilege (80% coverage)
- **Threat**: Privilege escalation
- **Mitigations**: Least-privilege IAM, Group_106 restrictions, validator roles, GitHub OIDC, Terraform state locking
- **Gap**: Admin MFA not enforced

## 📈 Coverage Summary

**Overall STRIDE Coverage: 91.1%**

- ✅ **Tampering**: 100% (5/5)
- ✅ **Repudiation**: 100% (5/5)
- ✅ **Information Disclosure**: 100% (6/6)
- ⚠️ **Spoofing**: 83.3% (5/6) - MFA gap
- ⚠️ **DoS**: 83.3% (5/6) - WAF detection script update needed
- ⚠️ **Elevation of Privilege**: 80% (4/5) - MFA gap

## 🔍 Key Components Mapped

### Application Layer
- `src/index.py` - Main FastAPI application
- `src/entrypoint.py` - Middleware registration
- `src/routes/*` - API route handlers
- `src/services/*` - Business logic services
- `src/middleware/*` - Security middleware (JWT, rate limiting, security headers)

### Infrastructure
- `infra/modules/api-gateway/` - API Gateway configuration
- `infra/modules/ecs/` - ECS Fargate service
- `infra/modules/s3/` - S3 bucket with encryption
- `infra/modules/dynamodb/` - DynamoDB tables
- `infra/modules/iam/` - IAM roles and policies
- `infra/modules/monitoring/` - CloudWatch and CloudTrail
- `infra/modules/waf/` - AWS WAF configuration

## 📝 Using This Diagram

### For Security Reviews
1. Review each trust boundary for potential vulnerabilities
2. Verify mitigations are implemented as shown
3. Identify gaps (marked with ⚠️)

### For Threat Modeling
1. Use the diagram to identify attack vectors
2. Trace data flows to find potential interception points
3. Review trust boundaries for privilege escalation risks

### For Compliance
1. Map STRIDE categories to compliance requirements
2. Document implemented mitigations
3. Track gaps and remediation plans

## 🔄 Updating the Diagram

When security controls change:
1. Open the diagram in Draw.io
2. Update relevant components/mitigations
3. Adjust coverage percentages
4. Update this guide if structure changes

## 📚 Related Documents

- `STRIDE_COVERAGE_ANALYSIS.md` - Detailed implementation status
- `STRIDE_VERIFICATION_REPORT.md` - Verification of claims
- `stride-threat-level.md` - Threat level analysis
- `SECURITY.md` - Overall security documentation

---

**Last Updated**: 2025-01-27  
**Diagram Version**: 1.0  
**Coverage**: 91.1%


