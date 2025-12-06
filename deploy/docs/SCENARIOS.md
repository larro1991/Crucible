# Deployment Scenarios

## Scenario Comparison

| Feature | S1: Single | S2: Fleet | S3: Production |
|---------|------------|-----------|----------------|
| Nodes | 1 | 3 | 7+ |
| HA | No | No | Yes |
| GPU | No | No | Optional |
| Cost/mo | ~$30 | ~$80 | ~$500-1000 |
| Use Case | Testing | Fleet Dev | Production |

## Scenario 1: Single Node

### Architecture

```
┌─────────────────────────────────┐
│      AWS EC2 (t3.medium)        │
│                                 │
│  ┌───────────────────────────┐  │
│  │     All Services          │  │
│  │  - Forge                  │  │
│  │  - EMBER                  │  │
│  │  - CINDER Controller      │  │
│  │  - Crucible               │  │
│  │  - K3s                    │  │
│  └───────────────────────────┘  │
│                                 │
└─────────────────────────────────┘
```

### When to Use
- Learning the system
- Local development backup
- CI/CD test environment
- Budget-constrained testing

### Deployment

```bash
./scripts/deploy.sh aws-s1 -k mykey -r us-east-1
```

### Limitations
- No fault tolerance
- Limited resources
- No fleet testing

---

## Scenario 2: Multi-Node Fleet

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                      VPC                              │
│  ┌─────────────────────────────────────────────┐     │
│  │              Public Subnet                   │     │
│  │  ┌─────────┐                                │     │
│  │  │   ALB   │                                │     │
│  │  └────┬────┘                                │     │
│  └───────┼─────────────────────────────────────┘     │
│          │                                           │
│  ┌───────┼─────────────────────────────────────┐     │
│  │       │      Private Subnet                  │     │
│  │       ▼                                      │     │
│  │  ┌─────────────┐    ┌─────────────┐         │     │
│  │  │ Controller  │───▶│  Worker 1   │         │     │
│  │  │ (t3.medium) │    │ (t3.small)  │         │     │
│  │  └─────────────┘    └─────────────┘         │     │
│  │       │                                      │     │
│  │       │             ┌─────────────┐         │     │
│  │       └────────────▶│  Worker 2   │         │     │
│  │                     │ (t3.small)  │         │     │
│  │                     └─────────────┘         │     │
│  └──────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

### When to Use
- Fleet management development
- CINDER controller/agent testing
- Failover testing (manual)
- Multi-node workloads

### Deployment

```bash
./scripts/deploy.sh aws-s2 -k mykey
```

### Test Scenarios

1. **Fleet Registration**: Workers auto-register with controller
2. **Health Monitoring**: Controller tracks worker health
3. **Task Distribution**: Deploy workloads across workers
4. **Node Failure**: Stop worker, verify detection

---

## Scenario 3: Production

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS VPC                              │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │                  Public Subnet                      │     │
│  │  ┌─────────┐              ┌─────────┐              │     │
│  │  │   ALB   │              │ Bastion │              │     │
│  │  └────┬────┘              └─────────┘              │     │
│  └───────┼────────────────────────────────────────────┘     │
│          │                                                   │
│  ┌───────┼────────────────────────────────────────────┐     │
│  │       │           Private Subnet                    │     │
│  │       ▼                                             │     │
│  │  ┌──────────┐  ┌──────────┐                        │     │
│  │  │   CP 1   │◄►│   CP 2   │  (HA Control Plane)    │     │
│  │  └────┬─────┘  └────┬─────┘                        │     │
│  │       │             │                               │     │
│  │       ▼             ▼                               │     │
│  │  ┌──────────────────────────────────┐              │     │
│  │  │         Worker Pool               │              │     │
│  │  │  ┌────┐  ┌────┐  ┌────┐          │              │     │
│  │  │  │ W1 │  │ W2 │  │ W3 │  (Auto)  │              │     │
│  │  │  └────┘  └────┘  └────┘          │              │     │
│  │  └──────────────────────────────────┘              │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────┐              │     │
│  │  │         GPU Pool                  │              │     │
│  │  │  ┌────────┐  ┌────────┐          │              │     │
│  │  │  │ GPU 1  │  │ GPU 2  │  (LLM)   │              │     │
│  │  │  └────────┘  └────────┘          │              │     │
│  │  └──────────────────────────────────┘              │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  EFS (Shared) + S3 (Backups) + Secrets Manager      │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### When to Use
- Production deployments
- High availability requirements
- GPU/LLM workloads
- Full feature testing

### Deployment

```bash
# With GPU nodes
./scripts/deploy.sh aws-s3 -k mykey

# Without GPU (saves ~$400/mo)
cd deploy/terraform/environments/scenario-3-production
terraform apply -var enable_gpu=false
```

### Test Scenarios

1. **HA Failover**: Stop CP1, verify CP2 takes over
2. **Auto-scaling**: Increase load, verify workers scale
3. **GPU Workloads**: Deploy LLM, verify GPU utilization
4. **Disaster Recovery**: Restore from S3 backup
5. **Network Partition**: Test split-brain handling

### Production Checklist

- [ ] Configure DNS for load balancer
- [ ] Set up SSL certificates
- [ ] Configure monitoring (Prometheus/Grafana)
- [ ] Set up log aggregation
- [ ] Configure backup schedule
- [ ] Document runbooks
- [ ] Test disaster recovery
- [ ] Set up alerting

---

## Cost Optimization

### Scenario 1
- Use spot instances (save 70%)
- Schedule shutdown during off-hours

### Scenario 2
- Use spot for workers
- Right-size based on actual usage

### Scenario 3
- Reserved instances for control plane (save 40%)
- Spot for workers with fallback to on-demand
- Auto-scaling based on metrics
- GPU instances only when needed

### Estimated Monthly Costs

| Component | S1 | S2 | S3 |
|-----------|-----|-----|-----|
| EC2 | $25 | $60 | $300 |
| NAT | $0 | $15 | $45 |
| ALB | $0 | $20 | $40 |
| EFS | $0 | $0 | $20 |
| S3 | $1 | $2 | $10 |
| Data | $5 | $10 | $50 |
| GPU | $0 | $0 | $400 |
| **Total** | **~$30** | **~$80** | **~$500-900** |
