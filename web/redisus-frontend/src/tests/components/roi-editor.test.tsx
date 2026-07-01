import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { RoiEditor } from '../../components/roi/RoiEditor';

describe('RoiEditor', () => {
  it('renderiza controles de ROI', () => {
    render(<RoiEditor open imageUrl="data:image/png;base64," initialRois={[]} onClose={vi.fn()} onSave={vi.fn()} />);
    expect(screen.getByText(/editor de roi/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /desenho livre/i })).toBeInTheDocument();
  });
});
