  ---                                                                                                                                                        
  Terminal 1 — llama.cpp engine (start this first)                                                                                                           
  cd /Users/mb/Desktop/Javier/SecondBrain/cerebro                                                                                                            
  make engine                                                                                                                                                
  Starts llama-server on port 8080. Leave it running.                                                                                                        
                  
  ---                                                                                                                                                        
  Terminal 2 — Cerebro backend
  cd /Users/mb/Desktop/Javier/SecondBrain/cerebro                                                                                                            
  source .venv/bin/activate                      
  CEREBRO_INFERENCE_BACKEND=llamacpp make run                                                                                                                
  Starts FastAPI on port 7842 using llama.cpp as the LLM.
                                                                                                                                                             
  ---                                                                                                                                                        
  Terminal 3 — Frontend
  cd /Users/mb/Desktop/Javier/SecondBrain/cerebro/ui/tray                                                                                                    
  npm run dev                                            
  Starts the React/Tauri dev server.  