import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  TextField,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  Alert,
  Snackbar,
} from '@mui/material';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';

interface Scan {
  id: number;
  filename: string;
  timestamp: string;
}

interface ScanDetail extends Scan {
  text: string;
  structured: Record<string, any>;
}

function App() {
  const [ragQuery, setRagQuery] = useState('');
  const [ragResults, setRagResults] = useState<any[]>([]);
  const [agentTask, setAgentTask] = useState('');
  const [agentResult, setAgentResult] = useState<any>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [selectedScan, setSelectedScan] = useState<ScanDetail | null>(null);
  const [backendStatus, setBackendStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/health`);
        setBackendStatus(res.data);
        setSnackbar({ open: true, message: 'Backend connected', severity: 'success' });
      } catch (e) {
        console.error('Backend not available:', e);
        setBackendStatus({ status: 'unavailable', error: String(e) });
        setSnackbar({ open: true, message: 'Backend unavailable', severity: 'error' });
      }
    };
    checkBackend();
    fetchScans();
  }, []);

  const fetchScans = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/scans`);
      setScans(res.data);
    } catch (e) {
      console.error('Failed to fetch scans', e);
    }
  };

  const fetchScanDetail = async (id: number) => {
    try {
      const res = await axios.get(`${BACKEND_URL}/scans/${id}`);
      setSelectedScan(res.data);
    } catch (e) {
      console.error('Failed to fetch scan detail', e);
    }
  };

  const handleRagQuery = async () => {
    if (!ragQuery) return;
    setLoading(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/rag/query`, { query: ragQuery });
      setRagResults(res.data.results);
      setSnackbar({ open: true, message: `Found ${res.data.results.length} results`, severity: 'success' });
    } catch (e) {
      console.error('RAG query failed', e);
      setSnackbar({ open: true, message: 'RAG query failed', severity: 'error' });
    }
    setLoading(false);
  };

  const handleAgentTask = async () => {
    if (!agentTask) return;
    setLoading(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/agent/execute`, {
        task: agentTask,
        params: { text: 'Sample text for agent analysis' }
      });
      setAgentResult(res.data.result);
      setSnackbar({ open: true, message: 'Agent task completed', severity: 'success' });
    } catch (e) {
      console.error('Agent execution failed', e);
      setSnackbar({ open: true, message: 'Agent execution failed', severity: 'error' });
    }
    setLoading(false);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Receipts OCR + RAG + Agent
      </Typography>

      <Paper sx={{ p: 2, mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="body2">Backend:</Typography>
        <Chip
          label={backendStatus?.status === 'ok' ? 'Online' : 'Offline'}
          color={backendStatus?.status === 'ok' ? 'success' : 'error'}
          size="small"
        />
        {backendStatus?.status === 'ok' && (
          <Typography variant="caption">
            RAG: {backendStatus.rag_engine} | Agent: {backendStatus.agent_engine} | Scans: {backendStatus.scan_count}
          </Typography>
        )}
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              RAG Query
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                fullWidth
                size="small"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Ask about receipts..."
                onKeyDown={(e) => e.key === 'Enter' && handleRagQuery()}
              />
              <Button variant="contained" onClick={handleRagQuery} disabled={loading}>
                Search
              </Button>
            </Box>
            {ragResults.length > 0 && (
              <Box>
                <Typography variant="subtitle2">Results</Typography>
                <Paper variant="outlined" sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                  <pre style={{ margin: 0, fontSize: '0.75rem' }}>
                    {JSON.stringify(ragResults, null, 2)}
                  </pre>
                </Paper>
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Agent
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                fullWidth
                size="small"
                value={agentTask}
                onChange={(e) => setAgentTask(e.target.value)}
                placeholder="Task (e.g., summarize, categorize)"
                onKeyDown={(e) => e.key === 'Enter' && handleAgentTask()}
              />
              <Button variant="contained" onClick={handleAgentTask} disabled={loading}>
                Execute
              </Button>
            </Box>
            {agentResult && (
              <Box>
                <Typography variant="subtitle2">Result</Typography>
                <Paper variant="outlined" sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                  <pre style={{ margin: 0, fontSize: '0.75rem' }}>
                    {JSON.stringify(agentResult, null, 2)}
                  </pre>
                </Paper>
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Scans
            </Typography>
            <List dense>
              {scans.map((scan) => (
                <ListItem key={scan.id} button onClick={() => fetchScanDetail(scan.id)}>
                  <ListItemText
                    primary={scan.filename}
                    secondary={new Date(scan.timestamp).toLocaleString()}
                  />
                </ListItem>
              ))}
            </List>
            {selectedScan && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Scan Details</Typography>
                <Paper variant="outlined" sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                  <pre style={{ margin: 0, fontSize: '0.75rem' }}>
                    {JSON.stringify(selectedScan, null, 2)}
                  </pre>
                </Paper>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled">
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}

export default App;
