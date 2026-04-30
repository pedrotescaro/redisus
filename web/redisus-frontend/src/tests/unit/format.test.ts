import { describe, expect, it } from 'vitest';

import { formatBytes, getInitials, pluralize } from '../../lib/format';

describe('formatadores', () => {
  it('formata bytes', () => {
    expect(formatBytes(1024)).toBe('1.0 KB');
  });

  it('gera iniciais', () => {
    expect(getInitials('Ana Maria Souza')).toBe('AM');
  });

  it('pluraliza labels', () => {
    expect(pluralize(1, 'paciente', 'pacientes')).toBe('1 paciente');
    expect(pluralize(2, 'paciente', 'pacientes')).toBe('2 pacientes');
  });
});
