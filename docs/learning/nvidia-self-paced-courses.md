# NVIDIA - self-paced courses z katalogu szkoleń

Źródło: `NVIDIA Training Course Catalog`, April 2026, plik PDF przesłany w rozmowie.

Zakres: tylko kursy oznaczone w katalogu jako **Self-paced Courses**. Pominąłem warsztaty instructor-led i egzaminy certyfikacyjne.

## Legenda priorytetu

- A - najwyższy priorytet dla AI infra / LLM inference / performance engineering
- B - przydatne uzupełnienie
- C - domenowe albo poboczne względem celu inference/infra

## Najbardziej istotne dla ścieżki AI infra / LLM inference

- Sizing LLM Inference Systems
- Introduction to NVIDIA NIMs Microservices
- The Art of Compressing LLMs: Pruning, Distillation, and Quantization Demystified
- Find the Bottleneck: Optimize AI Pipelines with Nsight Systems
- Optimizing CUDA Machine Learning Codes With Nsight Profiling Tools
- Getting Started with Accelerated Computing in Modern CUDA C++
- Use GPUs To Accelerate RAG Pipelines with Vector Databases
- Structure From Chaos: Accelerate GraphRAG With cuGraph and NVIDIA NIM
- Introduction to Deploying RAG Pipelines for Production at Scale
- AI Infrastructure and Operations Fundamentals
- Run:ai Platform Deployment
- BlueField DPU Administration
- InfiniBand Network Administration
- The Fundamentals of RDMA Programming

## Self-paced Courses for Developers

| Obszar | Tytuł | Opis | Narzędzia / biblioteki / frameworki | Czas | Cena | Certyfikat | Priorytet |
|---|---|---|---|---:|---:|---|---|
| Accelerated Computing | An Even Easier Introduction to CUDA | Podstawy pisania masowo równoległych kerneli CUDA: uruchamianie kerneli, organizacja wątków, zarządzanie pamięcią CPU/GPU i podstawowe profilowanie. | CUDA C++ | 1 h | Free | N/A | A |
| Accelerated Computing | Find the Bottleneck: Optimize AI Pipelines with Nsight Systems | Identyfikacja i usuwanie bottlenecków wydajnościowych w pipeline'ach AI z użyciem profilowania i oznaczania zakresów pracy. | Python, NVIDIA Nsight Systems, NVTX, PyTorch, PyNvVideoCodec, CV-CUDA, OpenCV, FFmpeg | 3 h | $30 | N/A | A |
| Accelerated Computing | Fundamentals of Accelerated Computing with CUDA Python | Przyspieszanie programów Python przez tworzenie i uruchamianie kerneli CUDA z użyciem Numba. | Numba, CUDA, Python | 8 h | $90 | Yes | A |
| Accelerated Computing | Getting Started with Accelerated Computing in Modern CUDA C++ | Pisanie, kompilowanie i uruchamianie kodu GPU; biblioteki CUDA; migracja pamięci CPU/GPU; implementacja własnych algorytmów. | CUDA, Nsight | 8 h | $90 | Yes | A |
| Accelerated Computing | GPU Acceleration with the C++ Standard Library | Pisanie prostych, przenośnych aplikacji parallel-first w standardowym C++, kompilowanych pod środowiska akcelerowane przez GPU. | NVIDIA HPC SDK | 2 h | $90 | N/A | B |
| Accelerated Computing | Nsight Analysis System: Build Custom Python Analysis Scripts | Budowanie własnych skryptów analitycznych w Pythonie do automatycznego wykrywania i podsumowywania bottlenecków aplikacji. | Python, NVIDIA Nsight Systems | 2 h | $30 | N/A | A |
| Accelerated Computing | Optimizing CUDA Machine Learning Codes With Nsight Profiling Tools | Praktyczne użycie Nsight Systems i Nsight Compute do profilowania i optymalizacji kodu CUDA/ML. | NVIDIA Nsight Systems, NVIDIA Nsight Compute | 2 h | $30 | N/A | A |
| Accelerated Computing | Scaling GPU-Accelerated Applications with the C++ Standard Library | Skalowanie aplikacji parallel-first w standardowym C++ na środowiska GPU bez dużych zmian w kodzie źródłowym. | Brak danych w PDF | 2 h | $30 | N/A | B |
| Data Science | Accelerate Data Science and Leverage Foundation Models in Digital Biology | Wykorzystanie foundation models i platformy NVIDIA do przyspieszania workflow w biologii cyfrowej. | NVIDIA HPC SDK, MPI | 2 h | $30 | N/A | C |
| Data Science | Accelerating Clustering Algorithms to Achieve the Highest Performance | Przyspieszanie algorytmów klastrowania, takich jak K-Means, DBSCAN i HDBSCAN, na GPU. | RAPIDS, cuDF, cuML | 2 h | $30 | N/A | B |
| Data Science | Accelerating End-to-End Data Science Workflows | Użycie narzędzi GPU-accelerated do szybszych, bardziej skalowalnych i tańszych workflow data science. | Brak danych w PDF | 8 h | $90 | Yes | B |
| Data Science | Accelerating Portfolio Optimization | Przyspieszanie pełnego workflow optymalizacji portfela. | Brak danych w PDF | 2 h | $30 | N/A | C |
| Data Science | Analyzing and Visualizing Large Data Interactively using Accelerated Computing | Budowanie responsywnych, interaktywnych dashboardów dla dużych datasetów z użyciem bibliotek GPU-accelerated. | RAPIDS, cuDF, XGBoost, cuML, cuGraph, Dask, cuPy, pandas, Polars, NumPy, Bokeh | 2 h | $30 | N/A | B |
| Data Science | Best Practices in Feature Engineering for Tabular Data With GPU Acceleration | Poprawa jakości modeli na dużych datasetach przez feature engineering z bibliotekami GPU-accelerated. | RAPIDS, cuDF, cuML, XGBoost | 2 h | $30 | N/A | B |
| Data Science | Exploring Adversarial Machine Learning | Ryzyka bezpieczeństwa w ML, typowe podatności oraz praktyczne budowanie ataków na modele. | PyTorch, pandas, NumPy | 8 h | $90 | Yes | B |
| Data Science | Structure From Chaos: Accelerate GraphRAG With cuGraph and NVIDIA NIM | Integracja LLM, NVIDIA NIM i cuGraph w graph-based AI dla złożonych, powiązanych danych. | cuGraph, NVIDIA NIM, NVIDIA NeMo | 2 h | $30 | N/A | A |
| Data Science | Use GPUs To Accelerate RAG Pipelines with Vector Databases | Optymalizacja workloadów baz wektorowych na GPU w kontekście pipeline'ów RAG. | cuVS, CuPy, Milvus, OpenAI, Optuna | 2 h | $30 | N/A | A |
| Deep Learning | Advanced Federated Learning with NVIDIA FLARE | Zaawansowane federated learning: zastosowania, prywatność danych, bezpieczeństwo i regulacje. | NVIDIA FLARE, NumPy, PyTorch | 8 h | $90 | Yes | C |
| Deep Learning | Applying AI Weather Models with NVIDIA Earth-2 | Integracja nowoczesnych modeli AI do prognozowania pogody z własnymi workflow. | Earth2Studio | 3 h | $30 | N/A | C |
| Deep Learning | Build High-Performance and AI-Enabled Sensor Processing Applications | Budowanie, wdrażanie i skalowanie aplikacji przetwarzania sensorów z AI. | NVIDIA Holoscan SDK, Holohub, CuPy, PyTorch | 3 h | $30 | N/A | B |
| Deep Learning | Building A Brain in 10 Minutes | Krótki notebook pokazujący biologiczną inspirację wczesnych sieci neuronowych. | TensorFlow 2 | 10 min | Free | N/A | C |
| Deep Learning | Building AI Agents with Multimodal Models | Tworzenie multimodalnych modeli sieci neuronowych obsługujących różne typy danych i techniki fuzji. | PyTorch, CLIP | 8 h | $90 | Yes | B |
| Deep Learning | Building Real-Time Video AI Applications | Przekształcanie surowego strumienia wideo z kamer w real-time insights oparte na deep learning. | NVIDIA pre-trained inference models | 8 h | $90 | Yes | B |
| Deep Learning | Decentralized AI at Scale with NVIDIA FLARE | Implementacja prywatnościowo-bezpiecznego, rozproszonego machine learningu z NVIDIA FLARE. | NVIDIA FLARE, NumPy, PyTorch | 4 h | Free | N/A | C |
| Deep Learning | Disaster Risk Monitoring Using Satellite Imagery | Wdrożenie modelu deep learning do automatyzacji use case'ów zarządzania katastrofami na danych satelitarnych. | NVIDIA DALI, NVIDIA TAO Toolkit, NVIDIA TensorRT, NVIDIA Triton Inference Server | 8 h | $90 | Yes | B |
| Deep Learning | Get Started with Highly Accurate Custom ASR for Speech AI | Budowanie, trenowanie, fine-tuning i wdrażanie GPU-accelerated usługi ASR z funkcjami customowymi. | NVIDIA Riva, NVIDIA NeMo | 3 h | $30 | N/A | B |
| Deep Learning | Getting Started with AI on Jetson Nano | Budowanie i trenowanie datasetu oraz modelu klasyfikacyjnego na NVIDIA Jetson Nano. | PyTorch, NVIDIA Jetson Nano | 8 h | Free | Yes | C |
| Deep Learning | Getting Started with Deep Learning | Podstawy deep learningu przez ćwiczenia z computer vision i NLP. | PyTorch | 8 h | $90 | Yes | B |
| Deep Learning | Integrating Sensors with NVIDIA DRIVE | Integracja wybranego sensora z platformą NVIDIA DRIVE. | C++, DriveWorks | 4 h | $30 | N/A | C |
| Deep Learning | Introduction to Federated Learning with NVIDIA FLARE | Wprowadzenie do NVIDIA Federated Learning Application Runtime Environment dla naukowców i developerów. | NVIDIA FLARE, NumPy, PyTorch | 2 h | Free | N/A | C |
| Deep Learning | Introduction to Graph Neural Networks | Podstawy, implementacje i zastosowania graph neural networks z ćwiczeniami hands-on. | Brak danych w PDF | 2 h | $30 | N/A | B |
| Deep Learning | Medical AI Development with MONAI: Interactive Annotation Using NVIDIA NIM Microservices | Budowanie end-to-end workflow medical AI z wykorzystaniem najnowszych narzędzi. | MONAI SDKs | 4 h | $30 | N/A | C |
| Generative AI / LLM | Agentic AI Explained | Wprowadzenie do agentic AI: autonomiczne agenty, które postrzegają, rozumują, działają i uczą się w dynamicznym środowisku. | Brak danych w PDF | 1 h | Free | N/A | A |
| Generative AI / LLM | An Introduction to NVIDIA Cosmos for Physical AI | Wprowadzenie hands-on do NVIDIA Cosmos: world foundation models, tokenizery, guardrails i pipeline curacji danych. | Brak danych w PDF | 2 h | $30 | N/A | B |
| Generative AI / LLM | Augment your LLM Using Retrieval Augmented Generation | Wprowadzenie do architektury RAG łączącej retrieval z generowaniem odpowiedzi. | Brak danych w PDF | 1 h | Free | N/A | A |
| Generative AI / LLM | Build a Deep Research Agent | Budowa i wdrożenie własnego deep research agenta z użyciem blueprintów NVIDIA. | Python, NVIDIA NIM, NVIDIA NeMo, NVIDIA Nemotron, AI-Q Research Assistant Blueprint, NVIDIA RAG Blueprint, Milvus, Tavily Search API, Docker | 4 h | $30 | N/A | A |
| Generative AI / LLM | Building Agentic AI Applications with LLMs | Projektowanie agentów, którzy pobierają i rafinują informacje, routują zapytania i wykonują zadania współbieżnie z LangGraph. | Python, PyTorch, NVIDIA NIM, build.nvidia.com, LangChain, LangGraph | 8 h | $90 | Yes | A |
| Generative AI / LLM | Building LLM Applications With Prompt Engineering | Fundamenty budowy aplikacji LLM z wykorzystaniem prompt engineering. | NVIDIA NIM, LangChain, Llama 3.1 | 8 h | $90 | Yes | B |
| Generative AI / LLM | Building RAG Agents with LLMs | Praktyczne wdrażanie systemów RAG/agentic z naciskiem na implementację pod realne obciążenia użytkowników i modeli. | Brak danych w PDF | 8 h | $90 | Yes | A |
| Generative AI / LLM | Domain-Adaptive Pre-Training: Tailoring LLMs for Specialized Applications | End-to-end lab budowania domain-specific LLM przez domain-adaptive pre-training. | Python, NVIDIA NeMo, NVIDIA NeMo Curator | 4 h | $30 | N/A | A |
| Generative AI / LLM | Evaluation and Light Customization of Large Language Models | Praktyczna ścieżka od ewaluacji LLM do lekkiego fine-tuningu i modelu bardziej dopasowanego domenowo. | Python, NVIDIA NeMo, NVIDIA NeMo Microservices (Evaluator, Customizer), Docker, MLflow | 3 h | $90 | N/A | A |
| Generative AI / LLM | Evaluating RAG and Semantic Search Systems | Ewaluacja RAG i semantic search: metryki domenowe, dane temporalne oraz oddzielna ocena retrieval i generation. | Brak danych w PDF | 3 h | $30 | N/A | A |
| Generative AI / LLM | Generative AI Explained | Przegląd pojęć, zastosowań, wyzwań i szans związanych z generative AI. | Brak danych w PDF | 2 h | Free | N/A | B |
| Generative AI / LLM | Generative AI with Diffusion Models | Głębsze wejście w denoising diffusion models używane w pipeline'ach text-to-image. | Brak danych w PDF | 8 h | $90 | Yes | C |
| Generative AI / LLM | Getting Started with NVIDIA Tools for Generative AI in Digital Health | Przegląd NVIDIA-optimized LLM, reasoning i agentic LLM systems z naciskiem na wdrożenie i customizację w digital health. | Brak danych w PDF | 2 h | Free | N/A | C |
| Generative AI / LLM | Introduction to Deploying RAG Pipelines for Production at Scale | Praktyki wdrażania produkcyjnego RAG: lokalne deploymenty, observability i zarządzanie środowiskiem. | NVIDIA NIMs, Kubernetes, Helm, Grafana, Prometheus | 4 h | $90 | Yes | A |
| Generative AI / LLM | Introduction to Multi-Modal Data Curation | Wprowadzenie do NeMo Curator do GPU-accelerated curacji tekstu, obrazów i wideo oraz generowania danych syntetycznych. | Brak danych w PDF | 1 h | Free | N/A | B |
| Generative AI / LLM | Introduction to NVIDIA NIMs Microservices | Kluczowe pojęcia potrzebne do budowy, wdrażania i skalowania aplikacji AI z użyciem NIM. | NVIDIA NIM Inference Microservices, Docker | 2 h | Free | N/A | A |
| Generative AI / LLM | Introduction to Transformer-Based Natural Language Processing | Jak transformery budują nowoczesne LLM; zastosowania NLP: klasyfikacja, NER, atrybucja autora, QA. | Brak danych w PDF | 6 h | $30 | N/A | B |
| Generative AI / LLM | Rapid Application Development with Large Language Models (LLMs) | Szybkie tworzenie aplikacji LLM z użyciem open-source ecosystemu, pretrained LLM i popularnych frameworków. | Python, PyTorch, Hugging Face, Transformers, LangChain, LangGraph | 8 h | $90 | Yes | A |
| Generative AI / LLM | Sizing LLM Inference Systems | Hands-on analiza streamingu, prefill, decoding, trade-offów throughput/latency, tensor parallelism i in-flight batching. | Brak danych w PDF | 3 h | $30 | N/A | A |
| Generative AI / LLM | Streamlining Drug Discovery with NVIDIA BioNeMo NIM Microservices and Blueprints | Zastosowanie BioNeMo NIM Microservices i blueprintów do przyspieszania drug discovery oraz analizy danych biochemicznych. | Brak danych w PDF | 2 h | Free | N/A | C |
| Generative AI / LLM | Synthetic Tabular Data Generation Using Transformers | Użycie transformerów do generowania syntetycznych danych tabelarycznych. | Brak danych w PDF | 4 h | $30 | N/A | C |
| Generative AI / LLM | Techniques for Improving the Effectiveness of RAG Systems | Techniki podnoszące jakość RAG z proof-of-concept do realnego aktywa produkcyjnego. | NVIDIA NIMs, LangChain, Redis, Next.js, FastAPI, Docker Compose | 4 h | $30 | N/A | A |
| Generative AI / LLM | The Art of Compressing LLMs: Pruning, Distillation, and Quantization Demystified | Model compression: redukcja rozmiaru i kosztu obliczeniowego modelu przy zachowaniu profilu jakości. | Brak danych w PDF | 8 h | $90 | Yes | A |
| Simulation and Physical AI | A Beginner's Guide to Autonomous Robots | Wprowadzenie do robotów autonomicznych, architektury robotycznej i wysokopoziomowej struktury software'u autonomii. | Brak danych w PDF | 1 h | Free | N/A | C |
| Simulation and Physical AI | Accelerating Computer-Aided Engineering (CAE) with NVIDIA AI Physics Technology | Budowanie i wdrażanie AI surrogate models dla aerodynamiki zewnętrznej jako alternatywy dla kosztownych symulacji CFD. | Python, PyTorch, PyVista, DGL, NVIDIA Physics NeMo, NVIDIA Omniverse | 8 h | $90 | Yes | C |
| Simulation and Physical AI | Accelerating ROS 2 Workloads With NVIDIA GPU-Powered Libraries and AI Models | Przyspieszanie workloadów ROS 2 bibliotekami GPU-powered dla AI i robotyki. | Brak danych w PDF | 3 h | $30 | N/A | C |
| Simulation and Physical AI | An Introduction to AI-Based Robot Development With Isaac ROS | Wprowadzenie do NVIDIA Isaac ROS jako frameworka robotycznego opartego na ROS. | Isaac ROS, NITROS | 0.5 h | Free | N/A | C |
| Simulation and Physical AI | An Introduction to Developing With NVIDIA Omniverse | Podstawy użycia Omniverse Kit SDK i szablonów do budowy aplikacji Omniverse. | Omniverse | 2 h | Free | N/A | C |
| Simulation and Physical AI | An Introduction to Robot Learning and Isaac Lab | Podstawy robot learning oraz wprowadzenie do NVIDIA Isaac Lab. | Isaac Lab | 3 h | Free | N/A | C |
| Simulation and Physical AI | Building AI-Powered Material Generation for Omniverse With DGX Cloud | Tworzenie rozszerzenia Omniverse generującego realistyczne materiały 3D z opisu natural language. | Omniverse, OpenUSD, NVIDIA NIM, PyTorch | 2 h | Free | N/A | C |
| Simulation and Physical AI | Building and Deploying Digital Twin Applications With Omniverse Kit App Streaming | Budowanie, konteneryzacja, deployment i rozszerzanie interaktywnych aplikacji 3D streamowanych do klientów webowych. | Omniverse | 1.5 h | $30 | N/A | C |
| Simulation and Physical AI | Creating an Omniverse Extension With Python | Tworzenie rozszerzenia Omniverse z interaktywnym UI i mapowaniem komend aplikacji do kodu. | Omniverse | 2 h | Free | N/A | C |
| Simulation and Physical AI | Develop, Simulate, and Deploy Robot Intelligence With General Robotics | End-to-end proces rozwoju robotyki z General Robotics GRID powered by NVIDIA Isaac Sim. | Brak danych w PDF | 1 h | Free | N/A | C |
| Simulation and Physical AI | Developing Robots With Software-in-the-Loop (SIL) In Isaac Sim | Podstawy Software-in-the-Loop i zastosowanie SIL w robotyce z NVIDIA Isaac Sim i ROS 2. | Isaac Sim | 2 h | Free | N/A | C |
| Simulation and Physical AI | Extend Omniverse Kit Applications for Building Digital Twins | Tworzenie aplikacji digital twin opartych o OpenUSD: agregacja danych, interaktywność i symulacja fizyki. | Omniverse | 2 h | Free | N/A | C |
| Simulation and Physical AI | Fundamentals of Working With OpenUSD | Podstawy pracy z Universal Scene Description (OpenUSD). | OpenUSD | 2 h | Free | N/A | C |
| Simulation and Physical AI | Generating High-Quality Motion Data for Robotics With MobilityGen | Wprowadzenie do MobilityGen do generowania high-fidelity motion data dla robotów mobilnych. | Brak danych w PDF | 1.5 h | Free | N/A | C |
| Simulation and Physical AI | Getting Started: Simulating Your First Robot in Isaac Sim | Budowanie prostego robota w Isaac Sim z komponentów typu chassis, wheels i joints. | Isaac Sim | 1.5 h | Free | N/A | C |
| Simulation and Physical AI | Ingesting Robot Assets and Simulating Your Robot in Isaac Sim | Importowanie i symulowanie robotów w Isaac Sim jako kontynuacja podstawowej symulacji robota. | Isaac Sim | 1 h | Free | N/A | C |
| Simulation and Physical AI | Leveraging ROS 2 and Hardware-in-the-Loop (HIL) in Isaac Sim | Przejście od symulacji do real-world deployment z ROS 2, Isaac Sim i NVIDIA Jetson. | Isaac Sim | 2 h | Free | N/A | C |
| Simulation and Physical AI | Software-in-the-Loop Testing for Robots With OpenUSD, Isaac Sim, and ROS | Testowanie i walidacja robotów AI-driven w środowisku digital twin z SIL. | OpenUSD, Isaac Sim, ROS | 2 h | Free | N/A | C |
| Simulation and Physical AI | Synthetic Data Generation for Perception Model Training in Isaac Sim | Trenowanie i wdrożenie modelu perception z użyciem synthetic data generation dla dynamicznych zadań robotycznych. | Brak danych w PDF | 2 h | Free | N/A | C |
| Simulation and Physical AI | Train Your First Robot in Isaac Lab | Hands-on start z reinforcement learning i physical AI w Isaac Lab. | Isaac Sim, Isaac Lab | 3 h | Free | N/A | C |
| Simulation and Physical AI | Train Your Second Robot in Isaac Lab | Głębsze wejście w Isaac Lab przez konfigurację i trening robota UR10 do konkretnego zadania. | Isaac Lab | 2 h | Free | N/A | C |
| Simulation and Physical AI | Training Healthcare Robotics From Scratch Using Isaac for Healthcare | Symulacje, dane syntetyczne, curacja datasetów, fine-tuning GR00T N1 VLA i testy robotic ultrasound w symulacji. | Isaac for Healthcare | 4 h | Free | N/A | C |
| Simulation and Physical AI | Transferring Robot Learning Policies From Simulation to Reality | Sim-to-real: dobre praktyki i typowe pułapki przy przenoszeniu polityk robot learning do rzeczywistości. | Brak danych w PDF | 1 h | Free | N/A | C |

## Self-paced Courses for Infrastructure Professionals

| Obszar | Tytuł | Opis | Narzędzia / biblioteki / frameworki | Czas | Cena | Certyfikat | Priorytet |
|---|---|---|---|---:|---:|---|---|
| AI and Data Science | AI for All: From Basics to GenAI Practice | Intro do AI i GenAI dla osób zaczynających lub chcących uporządkować podstawy obecnego krajobrazu AI. | N/A | 4 h | Free | N/A | B |
| AI and Data Science | AI Infrastructure and Operations Fundamentals | Przegląd platformy, architektury hardware/software, deploymentu, licencjonowania, partycjonowania GPU, skalowania, walidacji, monitoringu i troubleshootingu. | N/A | 7 h | $50 | Yes | A |
| AI and Data Science | Run:ai Platform Deployment | End-to-end wprowadzenie do deploymentu, konfiguracji i weryfikacji platformy Run:ai. | Run:ai | 3 h | $50 | Yes | A |
| DGX | DGX Cloud Create Onboarding | Wprowadzenie dla administratorów i użytkowników DGX Cloud Create: zarządzanie platformą i uruchamianie workloadów AI. | Brak danych w PDF | 2 h | $50 | Yes | A |
| Networking | Ansible Essentials for Network Engineers | Moduły Ansible i playbooki dla nowoczesnych data center, z hands-on labem w środowiskach cloud. | Networking | 1.5 h | $50 | Yes | B |
| Networking | BlueField DPU Administration | Podstawy BlueField DPU jako platformy accelerated data center computing i start z developmentem usług data center. | NVIDIA DOCA SDK, BlueField DPUs | 4 h | $50 | Yes | A |
| Networking | Cable Validation Tool (CVT) Fundamentals | Użycie CVT do walidacji infrastruktury okablowania data center dla InfiniBand i Ethernet. | Networking | 2 h | Free | Yes | B |
| Networking | Cumulus Linux Essentials | Podstawy Cumulus Linux, start z konfiguracją software'u i fundamentalnymi ustawieniami. | Networking | 2 h | Free | Yes | B |
| Networking | Cumulus Linux Administration | Deployment, operacje i zarządzanie sieciami data center na Cumulus Linux: switche, VLAN, routing, VXLAN i EVPN. | Networking | Brak danych w PDF | Brak danych w PDF | Yes | A |
| Networking | Data Center Management Made Easy with NVIDIA UFM | Operowanie, zarządzanie i utrzymanie węzłów InfiniBand Fabric w data center z UFM jako narzędziem pivot. | Networking | 2.5 h | $50 | Yes | A |
| Networking | InfiniBand Essentials | Pierwsze kroki w InfiniBand: korzyści, zastosowania, warstwy architektury i podstawy zarządzania. | Networking | 1 h | Free | Yes | A |
| Networking | InfiniBand Network Administration | Instalacja, konfiguracja, zarządzanie, monitoring i troubleshooting sieci InfiniBand. | Networking | 6.5 h | $200 | Yes | A |
| Networking | Introduction to Networking | Podstawy sieci, najczęściej używane protokoły TCP/IP, Ethernet i wymagania data center. | Networking | 2 h | Free | Yes | B |
| Networking | MLXLink and MLXCables | Troubleshooting i analiza fizycznych charakterystyk linków w sieciach high-performance. | Networking | 2 h | Free | Yes | A |
| Networking | NetQ Deployment and Installation | Deployment, zarządzanie i optymalizacja NVIDIA NetQ w środowiskach data center i AI Factory. | Networking | 2 h | Free | Yes | A |
| Networking | Network Administration with NVIDIA ONYX Switch System | Administracja, konfiguracja i zarządzanie switchami Ethernet NVIDIA z użyciem NVIDIA Onyx OS. | Networking | 1 h | $100 | Yes | B |
| Networking | RDMA Over Converged Ethernet (RoCE) From A to Z | Czym jest RoCE, jak działa, na jakich typach sieci może działać i jak go konfigurować. | Networking | 0.5 h | Free | Yes | A |
| Networking | SONiC Essentials by NVIDIA | Wprowadzenie do SONiC i konfiguracji bazowej, w tym lab z provisionowaniem EVPN VXLAN fabric. | SONiC, EVPN, VXLAN | 2 h | Free | Yes | B |
| Networking | The Fundamentals of RDMA Programming | Krótkie wideo, quizy i ćwiczenia hands-on do zdobycia praktycznych podstaw programowania RDMA. | RDMA | 4 h | $50 | Yes | A |
| Software and Tools | Base Command Manager Administration | Przegląd Base Command Manager do zarządzania klastrami HPC/AI i workloadami. | N/A | 3.5 h | Free | Yes | A |
| Software and Tools | Data Center Management Made Easy With NVIDIA UFM | Możliwości, zalety i komponenty NVIDIA Unified Fabric Manager przez interaktywne moduły, wideo i symulatory. | N/A | 2.5 h | $50 | Yes | A |
| Software and Tools | NVIDIA AI Enterprise Deployment on BareMetal Kubernetes | Deployment, zarządzanie i walidacja produkcyjnych workloadów AI na BareMetal Kubernetes z NVIDIA AI Enterprise. | Kubernetes, NVIDIA AI Enterprise | 4 h | $100 | Yes | A |
| Software and Tools | NVIDIA AI Enterprise for Azure Professionals | Scenario-based training na przykładzie RAG: od developmentu do produkcyjnego deploymentu. | Brak danych w PDF | 10 h | $100 | Yes | A |
| Software and Tools | NVIDIA License System | NVIDIA License System i migracja z istniejącego rozwiązania licencyjnego do NLS. | Cloud License Service (CLS), Delegated License Service (DLS) | 3 h | Free | Yes | C |
